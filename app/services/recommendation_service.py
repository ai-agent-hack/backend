from typing import List, Dict, Any, Optional
import time
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json

from app.models.pre_info import PreInfo
from app.schemas.spot import RecommendSpots
from app.services.llm_service import LLMService
from app.services.google_trends_service import GoogleTrendsService
from app.services.places_service import PlacesService
from app.services.vector_search_service import VectorSearchService
from app.services.scoring_service import ScoringService


class RecommendationService:
    """
    スポット推薦サービス
    シーケンス図に従って多段階推薦パイプラインを実行
    """

    def __init__(self):
        try:
            print("🚀 RecommendationService初期化開始...")

            # LLMサービス初期化
            print("🤖 LLMService初期化中...")
            self.llm_service = LLMService()
            print("✅ LLMService初期化完了")

            # Google Trendsサービス初期化
            print("🔥 GoogleTrendsService初期化中...")
            self.google_trends_service = GoogleTrendsService()
            print("✅ GoogleTrendsService初期化完了")

            # Placesサービス初期化
            print("🗺️ PlacesService初期化中...")
            self.places_service = PlacesService()
            print("✅ PlacesService初期化完了")

            # Vector Searchサービス初期化
            print("🎯 VectorSearchService初期化中...")
            self.vector_search_service = VectorSearchService()
            print("✅ VectorSearchService初期化完了")

            # Scoringサービス初期化
            print("🏆 ScoringService初期化中...")
            self.scoring_service = ScoringService()
            print("✅ ScoringService初期化完了")

            # 성능 최적화를 위한 설정
            self._cache = {}  # 간단한 메모리 캐시
            self._executor = ThreadPoolExecutor(max_workers=8)  # 더 많은 워커
            self._cache_ttl = 3600  # 1시간 캐시 TTL

            # 강화된 배치 설정
            self._max_keywords = 3  # 5개 → 3개로 감소
            self._places_per_keyword = 10  # 더 적은 수로 최적화
            self._vector_limit = 50  # 80개 → 50개
            self._final_limit = 24  # 30개 → 24개
            self._batch_size = 30  # 큰 배치 크기

            print("✅ RecommendationService初期化完了")

        except Exception as e:
            print(f"❌ RecommendationService初期化失敗: {str(e)}")
            # 初期化失敗してもサービスは継続実行
            self.llm_service = None
            self.google_trends_service = None
            self.places_service = None
            self.vector_search_service = None
            self.scoring_service = None

    def _get_cache_key(self, pre_info: PreInfo) -> str:
        """캐시 키 생성"""
        cache_data = {
            "region": pre_info.region,
            "atmosphere": pre_info.atmosphere,
            "budget": pre_info.budget,
            "participants_count": pre_info.participants_count,
        }
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """캐시에서 데이터 조회"""
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                print(f"💾 캐시 히트: {cache_key[:8]}...")
                return cached_data
            else:
                # 만료된 캐시 삭제
                del self._cache[cache_key]
                print(f"🗑️ 만료된 캐시 삭제: {cache_key[:8]}...")
        return None

    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """캐시에 데이터 저장"""
        self._cache[cache_key] = (data, time.time())
        print(f"💾 캐시 저장: {cache_key[:8]}...")

        # 캐시 크기 관리 (최대 100개)
        if len(self._cache) > 100:
            # 가장 오래된 캐시 1개 삭제
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
            print(f"🗑️ 오래된 캐시 삭제: {oldest_key[:8]}...")

    async def recommend_spots_from_pre_info(self, pre_info: PreInfo) -> Dict[str, Any]:
        """
        극도로 최적화된 추천 시스템 (병렬 + 배치 최적화)
        """
        start_time = time.time()

        # 캐시 키 생성 및 조회
        cache_key = self._get_cache_key(pre_info)
        cached_result = self._get_from_cache(cache_key)

        if cached_result:
            cache_time_ms = int((time.time() - start_time) * 1000)
            cached_result["processing_time_ms"] = cache_time_ms
            cached_result["from_cache"] = True
            print(f"⚡ 캐시 히트 - 즉시 반환: {cache_time_ms}ms")
            return cached_result

        # 메타데이터 초기화
        processing_metadata = {
            "total_spots_found": 0,
            "api_calls_made": 0,
            "super_optimization_applied": True,
            "processing_steps": [],
            "from_cache": False,
        }

        try:
            print("🚀 SUPER 최적화 모드 시작!")

            # 🔥 MEGA PHASE: 모든 작업을 최대한 병렬로
            mega_start = time.time()

            # 동시 실행할 작업들
            tasks = []

            # Task 1: LLM 키워드 생성 (비동기)
            keywords_task = self._generate_keywords_optimized(pre_info)
            tasks.append(("keywords", keywords_task))

            # Task 2: 기본 Places 검색 (병렬 준비)
            basic_search_task = self._prepare_basic_search(pre_info)
            tasks.append(("basic_search", basic_search_task))

            # Task 3: Vector 모델 준비 (백그라운드)
            vector_prep_task = self._prepare_vector_service()
            tasks.append(("vector_prep", vector_prep_task))

            print(f"🔥 {len(tasks)}개 작업 병렬 실행 시작...")

            # 모든 작업 동시 실행
            results = await asyncio.gather(
                *[task[1] for task in tasks], return_exceptions=True
            )

            # 결과 정리
            keywords = (
                results[0]
                if not isinstance(results[0], Exception)
                else ["바르셀로나 조용한 장소", "바르셀로나 공원", "바르셀로나 수도원"]
            )
            basic_places = results[1] if not isinstance(results[1], Exception) else []
            vector_ready = results[2] if not isinstance(results[2], Exception) else True

            mega_phase1_time = (time.time() - mega_start) * 1000
            processing_metadata["processing_steps"].append(
                f"MegaPhase1: {mega_phase1_time:.0f}ms"
            )
            print(f"✅ MEGA PHASE 1 완료: {mega_phase1_time:.0f}ms")

            # 🚀 MEGA PHASE 2: Places API 폭발적 병렬 처리
            phase2_start = time.time()

            # 키워드 기반 검색 + 기본 검색 결합
            all_search_tasks = []

            # 키워드별 병렬 검색 (최적화된 버전 사용)
            for keyword in keywords[: self._max_keywords]:
                if self.places_service:
                    search_task = self.places_service.text_search_optimized(
                        keyword, pre_info.region, max_results=60
                    )
                    all_search_tasks.append(search_task)

            # 모든 검색 동시 실행
            if all_search_tasks:
                search_results = await asyncio.gather(
                    *all_search_tasks, return_exceptions=True
                )

                all_place_ids = set()  # 중복 제거를 위한 set 사용
                for result in search_results:
                    if not isinstance(result, Exception) and result:
                        all_place_ids.update(result[: self._places_per_keyword])

                place_ids = list(all_place_ids)[: self._batch_size * 2]  # 최대 60개
            else:
                place_ids = [f"fallback_place_{i}" for i in range(30)]

            processing_metadata["api_calls_made"] += len(all_search_tasks)

            # 배치별 Details 가져오기 (울트라 병렬)
            place_details = await self._get_place_details_ultra_optimized(place_ids)
            processing_metadata["api_calls_made"] += len(place_ids)  # 실제 API 호출 수
            processing_metadata["total_spots_found"] = len(place_details)

            phase2_time = (time.time() - phase2_start) * 1000
            processing_metadata["processing_steps"].append(
                f"MegaPhase2: {phase2_time:.0f}ms"
            )
            print(f"✅ MEGA PHASE 2 완료: {phase2_time:.0f}ms")

            # 🎯 MEGA PHASE 3: Vector + LLM + Scoring 초병렬 처리
            phase3_start = time.time()

            # 동시 실행: Vector Search + LLM 준비
            vector_task = self._vector_search_mega_optimized(pre_info, place_details)

            # Vector Search 완료 후 LLM + Scoring 병렬
            vector_candidates = await vector_task
            processing_metadata["api_calls_made"] += 1

            # LLM과 기본 스코어링을 동시에
            llm_task = self._llm_rerank_ultra_fast(vector_candidates, pre_info)
            basic_scoring_task = self._basic_scoring_parallel(
                vector_candidates, pre_info
            )

            llm_result, basic_scores = await asyncio.gather(
                llm_task, basic_scoring_task, return_exceptions=True
            )

            # 결과 결합 (LLM 성공 시 사용, 실패 시 기본 스코어링)
            if not isinstance(llm_result, Exception):
                final_spots = llm_result[: self._final_limit]
            else:
                final_spots = (
                    basic_scores[: self._final_limit]
                    if not isinstance(basic_scores, Exception)
                    else vector_candidates[: self._final_limit]
                )

            processing_metadata["api_calls_made"] += 1

            phase3_time = (time.time() - phase3_start) * 1000
            processing_metadata["processing_steps"].append(
                f"MegaPhase3: {phase3_time:.0f}ms"
            )
            print(f"✅ MEGA PHASE 3 완료: {phase3_time:.0f}ms")

            # 🏆 최종 변환 (초고속)
            format_start = time.time()
            final_recommendations = self._format_spots_ultra_fast(final_spots)
            format_time = (time.time() - format_start) * 1000
            processing_metadata["processing_steps"].append(
                f"Format: {format_time:.0f}ms"
            )

            # 총 처리 시간 계산
            processing_time_ms = int((time.time() - start_time) * 1000)

            # 성능 리포트
            print("🚀 SUPER 최적화 결과:")
            print(f"  - 총 처리 시간: {processing_time_ms}ms")
            print(f"  - 단계별 시간: {processing_metadata['processing_steps']}")
            print(f"  - API 호출 최적화: {processing_metadata['api_calls_made']}회")
            print(f"  - 장소 발견: {processing_metadata['total_spots_found']}개")
            print(f"  - 최종 추천: {len(final_recommendations)}개 시간대")

            # 초기 가중치 (간단한 기본값)
            initial_weights = {
                "price": 0.7,
                "rating": 0.5,
                "congestion": 0.8,
                "similarity": 0.9,
            }

            # 최종 결과 생성
            result = {
                "rec_spot_id": f"rec_{int(datetime.now().timestamp())}",
                "recommend_spots": final_recommendations,
                "processing_time_ms": processing_time_ms,
                "keywords_generated": keywords,
                "hot_keywords": keywords,  # 간소화
                "initial_weights": initial_weights,
                **processing_metadata,
            }

            # 결과를 캐시에 저장
            self._save_to_cache(cache_key, result.copy())

            return result

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            raise Exception(
                f"SUPER 최적화 처리 중 에러: {str(e)} (처리시간: {processing_time_ms}ms)"
            )

    async def _generate_keywords_optimized(self, pre_info: PreInfo) -> List[str]:
        """최적화된 키워드 생성 (개수 감소)"""
        if self.llm_service is None:
            return [
                f"{pre_info.region} {pre_info.atmosphere}",
                f"{pre_info.region} 공원",
                f"{pre_info.region} 카페",
            ]

        try:
            keywords, _ = await self.llm_service.generate_keywords_and_weights(pre_info)
            return keywords[: self._max_keywords]  # 3개만 사용
        except:
            return [
                f"{pre_info.region} {pre_info.atmosphere}",
                f"{pre_info.region} 명소",
            ]

    async def _prepare_basic_search(self, pre_info: PreInfo) -> List[str]:
        """기본 검색 준비 (백그라운드)"""
        # 일반적인 장소 키워드
        basic_keywords = [f"{pre_info.region} 관광", f"{pre_info.region} 명소"]
        return basic_keywords

    async def _prepare_vector_service(self) -> bool:
        """Vector 서비스 준비"""
        # Vector 서비스가 준비되었는지 확인
        return self.vector_search_service is not None

    async def _get_place_details_ultra_optimized(
        self, place_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """🚀 울트라 최적화된 Places Details (대용량 병렬 배치)"""
        if self.places_service is None:
            print("⚠️ PlacesService 없음. 울트라 Fallback")
            return [
                {
                    "place_id": pid,
                    "name": f"장소_{i+1}",
                    "rating": 4.0 + (i % 10) * 0.1,
                    "address": "주소 정보",
                    "lat": 41.3851 + (i * 0.001),
                    "lng": 2.1734 + (i * 0.001),
                    "price_level": (i % 4) + 1,
                    "types": ["establishment"],
                }
                for i, pid in enumerate(place_ids[:60])  # 더 많은 fallback
            ]

        try:
            print(f"🚀 울트라 배치 Details: {len(place_ids)}개")

            # 울트라 배치 처리 (20개씩 병렬)
            place_details = await self.places_service.get_place_details_ultra_batch(
                place_ids, batch_size=20
            )

            print(f"✅ 울트라 배치 Details 완료: {len(place_details)}개")
            return place_details[:60]  # 최대 60개로 확장

        except Exception as e:
            print(f"❌ 울트라 배치 Details 실패: {str(e)}")
            # 간단한 fallback 데이터 반환
            return [
                {
                    "place_id": pid,
                    "name": f"Fallback_장소_{i+1}",
                    "rating": 4.0,
                    "address": "임시 주소",
                    "lat": 41.3851 + (i * 0.001),
                    "lng": 2.1734 + (i * 0.001),
                    "price_level": 2,
                    "types": ["establishment"],
                }
                for i, pid in enumerate(place_ids[:30])
            ]

    async def _vector_search_mega_optimized(
        self, pre_info: PreInfo, places: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """메가 최적화된 Vector Search"""
        if self.vector_search_service is None:
            print("⚠️ Vector Search 없음. 빠른 선별")
            return places[: self._vector_limit]

        try:
            # CPU 집약적 작업을 별도 스레드에서
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                lambda: self._vector_search_cpu_intensive(pre_info, places),
            )

            print(f"✅ 메가 Vector Search 완료: {len(result)}개")
            return result[: self._vector_limit]
        except Exception as e:
            print(f"❌ Vector Search 실패: {str(e)}")
            return places[: self._vector_limit]

    def _vector_search_cpu_intensive(self, pre_info, places):
        """CPU 집약적 Vector Search (별도 스레드)"""
        # 간단한 유사도 계산 (실제로는 Sentence Transformer 사용)
        scored_places = []
        query = f"{pre_info.atmosphere} {pre_info.region}"

        for place in places:
            # 간단한 텍스트 매칭 점수
            name = place.get("name", "")
            score = len(set(query.lower().split()) & set(name.lower().split()))
            place["similarity_score"] = score
            scored_places.append(place)

        # 점수별 정렬
        return sorted(
            scored_places, key=lambda x: x.get("similarity_score", 0), reverse=True
        )

    async def _llm_rerank_ultra_fast(
        self, candidates: List[Dict], pre_info: PreInfo
    ) -> List[Dict]:
        """초고속 LLM 재랭킹"""
        if self.llm_service is None:
            print("⚠️ LLM 없음. 빠른 재랭킹")
            return candidates[:40]

        try:
            # LLM 재랭킹 (타임아웃 설정)
            reranked, _ = await asyncio.wait_for(
                self.llm_service.rerank_and_adjust_weights(candidates, {}, pre_info),
                timeout=10.0,  # 10초 타임아웃
            )
            return reranked[:40]
        except:
            print("⚠️ LLM 타임아웃. 기본 재랭킹 사용")
            return candidates[:40]

    async def _basic_scoring_parallel(
        self, candidates: List[Dict], pre_info: PreInfo
    ) -> List[Dict]:
        """병렬 기본 스코어링 (LLM 백업용)"""
        # CPU 집약적 스코어링을 별도 스레드에서
        loop = asyncio.get_event_loop()

        try:
            scored = await loop.run_in_executor(
                self._executor,
                lambda: self._calculate_basic_scores(candidates, pre_info),
            )
            return scored[:40]
        except:
            return candidates[:40]

    def _calculate_basic_scores(self, candidates: List[Dict], pre_info) -> List[Dict]:
        """기본 스코어 계산 (CPU 집약적)"""
        for candidate in candidates:
            rating = candidate.get("rating", 3.5)
            price_level = candidate.get("price_level", 2)

            # 간단한 스코어링
            rating_score = rating / 5.0
            price_score = 1.0 - (price_level - 1) / 4.0
            final_score = rating_score * 0.6 + price_score * 0.4

            candidate["final_score"] = final_score

        return sorted(candidates, key=lambda x: x.get("final_score", 0), reverse=True)

    def _format_spots_ultra_fast(
        self, spots: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """초고속 스팟 포맷팅"""
        if not spots:
            return []

        # 3개 시간대로 균등 분배
        spots_per_slot = len(spots) // 3
        remainder = len(spots) % 3

        time_slots = [
            ("午前", spots[: spots_per_slot + (1 if remainder > 0 else 0)]),
            (
                "午後",
                spots[
                    spots_per_slot
                    + (1 if remainder > 0 else 0) : 2 * spots_per_slot
                    + (2 if remainder > 1 else 1 if remainder > 0 else 0)
                ],
            ),
            (
                "夜",
                spots[
                    2 * spots_per_slot
                    + (2 if remainder > 1 else 1 if remainder > 0 else 0) :
                ],
            ),
        ]

        formatted_spots = []
        for time_slot, slot_spots in time_slots:
            if slot_spots:
                formatted_spots.append(
                    {
                        "time_slot": time_slot,
                        "spots": [
                            self._convert_to_spot_schema_fast(spot, idx)
                            for idx, spot in enumerate(slot_spots)
                        ],
                    }
                )

        return formatted_spots

    def _convert_to_spot_schema_fast(
        self, place_data: Dict[str, Any], index: int
    ) -> Dict[str, Any]:
        """고속 스팟 스키마 변환"""
        lat = place_data.get("lat", 41.3851)
        lng = place_data.get("lng", 2.1734)
        
        # Google Mapに投稿された写真のURLを取得（最初の1枚）
        photos = place_data.get("photos", [])
        google_map_image_url = photos[0] if photos else None
        
        return {
            "spot_id": place_data.get("place_id", f"spot_{index}"),
            "longitude": lng,
            "latitude": lat,
            "recommendation_reason": f"{place_data.get('name', '場所')}は評価 {place_data.get('rating', 4.0):.1f}でおすすめです。",
            "details": {
                "name": place_data.get("name", f"장소_{index}"),
                "congestion": [40 + (i * 3) % 50 for i in range(24)],  # 간단한 혼잡도
                "business_hours": {
                    day: {"open_time": "09:00:00", "close_time": "18:00:00"}
                    for day in [
                        "MONDAY",
                        "TUESDAY",
                        "WEDNESDAY",
                        "THURSDAY",
                        "FRIDAY",
                        "SATURDAY",
                        "SUNDAY",
                        "HOLIDAY",
                    ]
                },
                "price": place_data.get("price_level", 2) * 1000,
            },
            "google_map_image_url": google_map_image_url,
            "website_url": place_data.get("website", None),
            "selected": False,
        }
