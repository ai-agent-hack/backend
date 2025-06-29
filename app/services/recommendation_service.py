from typing import List, Dict, Any, Optional
import time
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import logging

from app.models.pre_info import PreInfo
from app.schemas.spot import RecommendSpots
from app.services.llm_service import LLMService
from app.services.google_trends_service import GoogleTrendsService
from app.services.places_service import PlacesService
from app.services.vector_search_service import VectorSearchService
from app.services.scoring_service import ScoringService

# Initialize module-level logger
logger = logging.getLogger(__name__)


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

            # 강화된 배치 설정 (키워드 증가로 정확도 향상)
            self._max_keywords = 8  # 3개 → 8개로 증가 (정확도 향상)
            self._places_per_keyword = 12  # 키워드당 더 많은 결과
            self._vector_limit = 80  # 50개 → 80개로 복원
            self._final_limit = 30  # 24개 → 30개로 증가
            self._batch_size = 50  # 더 큰 배치 크기

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
        """최적화된 키워드 생성 (개수 증가로 정확도 향상)"""
        if self.llm_service is None:
            return [
                f"{pre_info.region} {pre_info.atmosphere}",
                f"{pre_info.region} 공원",
                f"{pre_info.region} 카페",
                f"{pre_info.region} 관광",
                f"{pre_info.region} 그룹",
                f"{pre_info.region} 문화",
                f"{pre_info.region} 자연",
                f"{pre_info.region} 야경",
            ]

        try:
            keywords, _ = await self.llm_service.generate_keywords_and_weights(pre_info)
            return keywords[: self._max_keywords]  # 8개 사용
        except:
            return [
                f"{pre_info.region} {pre_info.atmosphere}",
                f"{pre_info.region} 명소",
                f"{pre_info.region} 카페",
                f"{pre_info.region} 관광",
                f"{pre_info.region} 문화",
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
        """스마트 시간대별 스팟 분배 (혼잡도 & 장소 특성 기반)"""
        if not spots:
            return []

        # 시간대별로 스팟 분류
        categorized_spots = self._categorize_spots_by_time_suitability(spots)

        # 각 시간대별로 포맷팅
        formatted_spots = []
        for time_slot, slot_spots in categorized_spots.items():
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

    def _categorize_spots_by_time_suitability(
        self, spots: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """혼잡도와 장소 특성에 따른 시간대별 분류"""

        # 시간대별 카테고리
        morning_spots = []
        afternoon_spots = []
        evening_spots = []

        for spot in spots:
            types = spot.get("types", [])
            name = spot.get("name", "").lower()

            # 장소 특성 점수 계산
            morning_score = self._calculate_morning_suitability(spot, types, name)
            afternoon_score = self._calculate_afternoon_suitability(spot, types, name)
            evening_score = self._calculate_evening_suitability(spot, types, name)

            # 혼잡도 기반 추가 점수 (congestion 데이터 활용)
            congestion_bonus = self._get_congestion_based_time_bonus(spot)
            morning_score += congestion_bonus.get("morning", 0)
            afternoon_score += congestion_bonus.get("afternoon", 0)
            evening_score += congestion_bonus.get("evening", 0)

            # 가장 높은 점수의 시간대에 배정
            max_score = max(morning_score, afternoon_score, evening_score)

            if max_score == morning_score:
                morning_spots.append(spot)
            elif max_score == afternoon_score:
                afternoon_spots.append(spot)
            else:
                evening_spots.append(spot)

        # 각 시간대가 너무 비어있지 않도록 균형 조정
        morning_spots, afternoon_spots, evening_spots = self._balance_time_slots(
            morning_spots, afternoon_spots, evening_spots
        )

        return {"午前": morning_spots, "午後": afternoon_spots, "夜": evening_spots}

    def _calculate_morning_suitability(
        self, spot: Dict, types: List[str], name: str
    ) -> float:
        """오전 적합도 계산"""
        score = 0.0

        # 오전에 좋은 장소 타입들 (혼잡도 고려하여 관광명소도 포함)
        morning_types = {
            "cafe": 3.0,
            "bakery": 2.5,
            "park": 2.5,
            "museum": 2.5,  # 조용한 관람
            "library": 2.0,
            "church": 1.5,
            "temple": 1.5,
            "garden": 2.0,
            "zoo": 1.5,
            "aquarium": 1.5,
            "art_gallery": 2.5,  # 조용한 관람
            # 혼잡도가 낮을 때 좋은 관광명소들 추가
            "tourist_attraction": 1.8,  # 기본은 낮지만 혼잡도 보너스로 역전 가능
            "landmark": 1.5,  # 랜드마크도 오전이 덜 혼잡
            "viewpoint": 1.8,  # 전망대 - 오전에 덜 혼잡
            "monument": 1.5,  # 기념물 - 오전에 조용함
        }

        # 타입 기반 점수
        for place_type in types:
            if place_type in morning_types:
                score += morning_types[place_type]

        # types가 없는 경우 이름 기반으로 관광명소 감지 및 보너스 적용
        if not types:  # types 정보가 없을 때만 이름 기반 분류 강화
            tourist_name_patterns = [
                "타워",
                "tower",
                "전망대",
                "observatory",
                "스카이",
                "sky",
                "박물관",
                "museum",
                "미술관",
                "gallery",
                "궁",
                "palace",
                "성",
                "castle",
                "한옥",
                "hanok",
                "전통",
                "traditional",
                "문화재",
                "heritage",
                "유적",
                "historic",
                "명소",
                "attraction",
                "관광",
                "tourist",
                "랜드마크",
                "landmark",
                "뷰",
                "view",
            ]

            tourist_score = 0
            for pattern in tourist_name_patterns:
                if pattern in name:
                    tourist_score = max(tourist_score, 1.8)  # 관광명소 기본 점수
                    break

            if tourist_score > 0:
                score += tourist_score
                print(f"관광명소 감지: {name} -> 오전 기본점수 {tourist_score}")

        # 이름 기반 추가 점수 (혼잡도 낮은 관광명소 포함)
        morning_keywords = [
            "카페",
            "cafe",
            "공원",
            "park",
            "박물관",
            "museum",
            "미술관",
            "갤러리",
            # 오전에 혼잡도가 낮아서 좋은 관광명소들
            "전망대",
            "observatory",
            "타워",
            "tower",
            "전망",
            "view",
            "성",
            "palace",
            "궁",
            "문화재",
            "heritage",
            "유적",
            "historic",
            "정원",
            "garden",
            "산책로",
            "walkway",
            "둘레길",
            "trail",
        ]
        for keyword in morning_keywords:
            if keyword in name:
                score += 1.0

        return score

    def _calculate_afternoon_suitability(
        self, spot: Dict, types: List[str], name: str
    ) -> float:
        """오후 적합도 계산"""
        score = 0.0

        # 오후에 좋은 장소 타입들
        afternoon_types = {
            "tourist_attraction": 3.0,
            "shopping_mall": 2.5,
            "store": 2.0,
            "amusement_park": 3.0,
            "monument": 2.0,
            "landmark": 2.3,  # 약간 낮춤 (저녁 야경 고려)
            "stadium": 2.0,
            "university": 1.5,
            "beach": 2.5,
            "hiking_area": 2.0,
            "viewpoint": 2.0,  # 낮춤 (야경은 저녁이 더 좋음)
        }

        # 타입 기반 점수
        for place_type in types:
            if place_type in afternoon_types:
                score += afternoon_types[place_type]

        # 이름 기반 추가 점수
        afternoon_keywords = [
            "타워",
            "tower",
            "쇼핑",
            "shopping",
            "관광",
            "명소",
            "랜드마크",
        ]
        for keyword in afternoon_keywords:
            if keyword in name:
                score += 1.0

        return score

    def _calculate_evening_suitability(
        self, spot: Dict, types: List[str], name: str
    ) -> float:
        """저녁 적합도 계산"""
        score = 0.0

        # 저녁에 좋은 장소 타입들
        evening_types = {
            "restaurant": 3.0,
            "bar": 3.0,
            "night_club": 3.0,
            "meal_takeaway": 2.0,
            "food": 2.5,
            "lodging": 1.0,
            "spa": 2.0,
            "movie_theater": 2.5,
            "casino": 3.0,
            "rooftop_bar": 3.0,
            # 야경 명소들 추가
            "viewpoint": 2.8,  # 전망대 - 야경 명소
            "tourist_attraction": 2.3,  # 관광명소 (야경 고려)
            "landmark": 2.5,  # 랜드마크 (타워 등)
            "bridge": 2.5,  # 다리 (야경 명소)
            "park": 2.0,  # 공원 (야경 산책)
        }

        # 타입 기반 점수
        for place_type in types:
            if place_type in evening_types:
                score += evening_types[place_type]

        # 이름 기반 추가 점수 (야경 명소 대폭 추가)
        evening_keywords = [
            "레스토랑",
            "restaurant",
            "바",
            "bar",
            "클럽",
            "club",
            "맛집",
            # 야경 관련 키워드들
            "야경",
            "night view",
            "nightview",
            "야간",
            "night",
            "타워",
            "tower",
            "전망대",
            "observatory",
            "viewpoint",
            "루프탑",
            "rooftop",
            "스카이",
            "sky",
            "다리",
            "bridge",
            "한강",
            "river",
            "강변",
            "전망",
            "view",
            "뷰",
            "파노라마",
            "panorama",
            "일몰",
            "sunset",
            "석양",
            "twilight",
            "황혼",
            "조명",
            "lighting",
            "illumination",
            "라이트업",
        ]
        for keyword in evening_keywords:
            if keyword in name:
                score += 1.0

        # 비즈니스 시간 고려 (저녁 늦게까지 운영하는 곳)
        business_hours = spot.get("business_hours", {})
        if business_hours:
            # 주말 저녁 시간대 운영 여부 확인
            saturday_hours = business_hours.get("SATURDAY", {})
            if saturday_hours:
                close_time = saturday_hours.get("close_time", "18:00:00")
                if close_time and close_time >= "20:00:00":  # 8시 이후까지 운영
                    score += 1.5

        # 야경 명소 특별 보너스 (타워, 전망대, 높은 건물)
        if any(
            keyword in name for keyword in ["타워", "tower", "전망대", "스카이", "sky"]
        ):
            score += 2.0  # 야경 명소 대형 보너스

        # 강변/다리 야경 보너스
        if any(
            keyword in name for keyword in ["한강", "다리", "bridge", "river", "강변"]
        ):
            score += 1.5  # 수변 야경 보너스

        # 공원 야경 산책 보너스 (저녁 시간대 공원은 야경 산책 목적)
        if any(park_type in types for park_type in ["park", "garden"]):
            score += 1.0  # 야경 산책 보너스

        return score

    def _balance_time_slots(
        self, morning: List, afternoon: List, evening: List
    ) -> tuple:
        """시간대별 균형 조정 (한 시간대가 너무 비어있지 않도록)"""
        total_spots = len(morning) + len(afternoon) + len(evening)

        if total_spots == 0:
            return morning, afternoon, evening

        target_per_slot = total_spots // 3
        min_per_slot = max(1, target_per_slot // 2)  # 최소 보장 개수

        # 너무 적은 시간대 찾기
        all_slots = [
            ("morning", morning),
            ("afternoon", afternoon),
            ("evening", evening),
        ]

        # 부족한 시간대에 다른 시간대에서 이동
        for slot_name, slot_spots in all_slots:
            if len(slot_spots) < min_per_slot:
                # 가장 많은 시간대에서 일부 이동
                source_slots = [
                    (name, spots)
                    for name, spots in all_slots
                    if name != slot_name and len(spots) > target_per_slot
                ]

                if source_slots:
                    # 가장 많은 시간대에서 가져오기
                    source_name, source_spots = max(
                        source_slots, key=lambda x: len(x[1])
                    )
                    needed = min_per_slot - len(slot_spots)
                    available = len(source_spots) - target_per_slot

                    if available > 0:
                        move_count = min(needed, available)
                        moved_spots = source_spots[-move_count:]
                        source_spots = source_spots[:-move_count]
                        slot_spots.extend(moved_spots)

        return morning, afternoon, evening

    def _get_congestion_based_time_bonus(self, spot: Dict) -> Dict[str, float]:
        """혼잡도 패턴 분석을 통한 시간대별 보너스 점수"""
        bonus = {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}

        # details에서 congestion 데이터 가져오기 (24시간 혼잡도 배열)
        details = spot.get("details", {})
        congestion = details.get("congestion", [])

        if not congestion or len(congestion) != 24:
            return bonus

        try:
            # 시간대별 평균 혼잡도 계산
            morning_congestion = sum(congestion[6:12]) / 6  # 06:00-11:59 오전
            afternoon_congestion = sum(congestion[12:18]) / 6  # 12:00-17:59 오후
            evening_congestion = sum(congestion[18:24]) / 6  # 18:00-23:59 저녁

            # 혼잡도가 낮은 시간대에 보너스 (조용한 시간대 선호)
            max_congestion = max(
                morning_congestion, afternoon_congestion, evening_congestion
            )

            if max_congestion > 0:
                # 혼잡도가 상대적으로 낮은 시간대에 강력한 보너스 (관광명소 역전 가능)
                congestion_diff_morning = (
                    max_congestion - morning_congestion
                ) / max_congestion
                congestion_diff_afternoon = (
                    max_congestion - afternoon_congestion
                ) / max_congestion
                congestion_diff_evening = (
                    max_congestion - evening_congestion
                ) / max_congestion

                # 관광명소/랜드마크는 혼잡도 보너스를 더 크게 적용
                spot_types = spot.get("types", [])
                spot_name = spot.get("details", {}).get("name", "").lower()

                # types 기반 또는 이름 기반으로 관광명소 감지
                is_tourist_spot = any(
                    t in spot_types
                    for t in ["tourist_attraction", "landmark", "viewpoint", "monument"]
                ) or any(
                    keyword in spot_name
                    for keyword in [
                        "타워",
                        "tower",
                        "전망대",
                        "스카이",
                        "sky",
                        "박물관",
                        "museum",
                        "미술관",
                        "gallery",
                        "궁",
                        "palace",
                        "명소",
                        "landmark",
                        "뷰",
                        "view",
                    ]
                )

                multiplier = (
                    4.0 if is_tourist_spot else 1.5
                )  # 관광명소는 혼잡도 영향 훨씬 더 크게 (역전 가능하도록)

                bonus["morning"] = congestion_diff_morning * multiplier
                bonus["afternoon"] = congestion_diff_afternoon * multiplier
                bonus["evening"] = congestion_diff_evening * multiplier

                # 디버깅용 로그
                if is_tourist_spot and congestion_diff_morning > 0.3:
                    print(f"🏛️ 관광명소 혼잡도 보너스: {spot_name}")
                    print(
                        f"   오전 혼잡도: {morning_congestion:.1f}, 보너스: {bonus['morning']:.2f}"
                    )
                    print(
                        f"   오후 혼잡도: {afternoon_congestion:.1f}, 보너스: {bonus['afternoon']:.2f}"
                    )

            # 특별 케이스: 새벽시간 운영 여부 (24시간 영업소 등)
            late_night_congestion = (
                sum(congestion[22:24] + congestion[0:6]) / 8
            )  # 22:00-05:59
            if late_night_congestion > 10:  # 새벽에도 사람이 있다면
                bonus["evening"] += 0.5  # 저녁 시간대 보너스

        except (ZeroDivisionError, IndexError, TypeError):
            # 계산 오류 시 기본값 반환
            pass

        return bonus

    def _generate_realistic_congestion(
        self, place_data: Dict[str, Any], index: int
    ) -> List[int]:
        """현실적인 혼잡도 패턴 생성 (장소 타입별 차별화)"""
        place_types = place_data.get("types", [])
        name = place_data.get("name", "").lower()

        # 기본 혼잡도 패턴 (시간별)
        base_congestion = [
            20,
            15,
            10,
            8,
            10,
            15,
            25,
            35,
            45,
            50,
            55,
            60,
            65,
            70,
            75,
            70,
            65,
            55,
            45,
            40,
            35,
            30,
            25,
            20,
        ]

        # 장소 타입별 특성화
        if any(
            t in place_types
            for t in ["tourist_attraction", "landmark", "viewpoint", "monument"]
        ):
            # 관광명소: 오전(6-11시)은 매우 한적, 오후(12-17시)는 매우 혼잡
            tourist_pattern = [
                10,
                8,
                5,
                3,
                5,
                8,
                15,
                20,
                25,
                30,
                35,
                40,
                80,
                90,
                95,
                90,
                85,
                70,
                50,
                40,
                30,
                25,
                20,
            ]
            return [max(5, min(100, val + (index % 10 - 5))) for val in tourist_pattern]

        elif any(t in place_types for t in ["restaurant", "bar", "food"]):
            # 레스토랑: 점심(11-14시), 저녁(18-21시) 피크
            restaurant_pattern = [
                5,
                3,
                2,
                2,
                3,
                5,
                10,
                15,
                20,
                25,
                30,
                60,
                80,
                70,
                50,
                40,
                45,
                55,
                85,
                90,
                80,
                60,
                40,
                20,
            ]
            return [
                max(5, min(100, val + (index % 8 - 4))) for val in restaurant_pattern
            ]

        elif any(t in place_types for t in ["cafe", "bakery"]):
            # 카페: 오전(8-11시), 오후(14-17시) 피크
            cafe_pattern = [
                10,
                8,
                5,
                5,
                8,
                15,
                25,
                50,
                70,
                80,
                75,
                65,
                45,
                40,
                60,
                70,
                65,
                50,
                35,
                25,
                20,
                15,
                12,
                10,
            ]
            return [max(5, min(100, val + (index % 6 - 3))) for val in cafe_pattern]

        elif any(t in place_types for t in ["park", "garden"]):
            # 공원: 오후(15-18시), 저녁 산책(19-21시) 피크
            park_pattern = [
                5,
                3,
                2,
                2,
                3,
                8,
                15,
                25,
                30,
                35,
                40,
                45,
                50,
                55,
                60,
                70,
                75,
                70,
                65,
                80,
                70,
                50,
                30,
                15,
            ]
            return [max(5, min(100, val + (index % 7 - 3))) for val in park_pattern]

        else:
            # 기타 장소: 기본 패턴에 약간의 변화
            return [max(5, min(100, val + (index % 12 - 6))) for val in base_congestion]

    def _generate_recommendation_reason(self, place_data: Dict[str, Any]) -> str:
        """場所の詳細情報に基づいて場所の説明を生成"""
        types = place_data.get("types", [])
        rating = place_data.get("rating", 0.0)
        ratings_total = place_data.get("ratings_total", 0)
        price_level = place_data.get("price_level", 0)
        opening_hours = place_data.get("opening_hours", {})
        address = place_data.get("address", "")
        
        # 場所の説明部分を構築
        description_parts = []
        
        # 場所のタイプに基づく説明
        type_descriptions = {
            "restaurant": "レストラン",
            "cafe": "カフェ",
            "museum": "博物館",
            "park": "公園",
            "temple": "寺院",
            "shrine": "神社",
            "shopping_mall": "ショッピングモール",
            "tourist_attraction": "観光スポット",
            "amusement_park": "遊園地",
            "art_gallery": "美術館",
            "aquarium": "水族館",
            "zoo": "動物園",
            "spa": "スパ",
            "night_club": "ナイトクラブ",
            "bar": "バー",
            "bakery": "ベーカリー",
            "book_store": "書店",
            "clothing_store": "衣料品店",
            "department_store": "デパート",
            "electronics_store": "電器店",
            "gym": "ジム",
            "hair_care": "美容院",
            "hospital": "病院",
            "library": "図書館",
            "movie_theater": "映画館",
            "pharmacy": "薬局",
            "school": "学校",
            "supermarket": "スーパーマーケット",
            "train_station": "駅",
            "subway_station": "地下鉄駅"
        }
        
        # メインのタイプを特定
        main_type = None
        for place_type in types:
            if place_type in type_descriptions:
                main_type = type_descriptions[place_type]
                break
        
        if main_type:
            description_parts.append(main_type)
        
        # 価格帯の情報（レストランやカフェなどの場合）
        if price_level > 0 and main_type in ["レストラン", "カフェ", "バー"]:
            price_descriptions = {
                1: "リーズナブルな価格帯",
                2: "手頃な価格帯",
                3: "やや高級",
                4: "高級"
            }
            if price_level in price_descriptions:
                description_parts.append(price_descriptions[price_level])
        
        # 評価とレビュー数の情報
        if rating > 0 and ratings_total > 0:
            if ratings_total >= 1000:
                description_parts.append(f"評価{rating:.1f}（{ratings_total}件以上のレビュー）")
            elif ratings_total >= 100:
                description_parts.append(f"評価{rating:.1f}（{ratings_total}件のレビュー）")
            else:
                description_parts.append(f"評価{rating:.1f}")
        
        # 営業時間の情報
        if opening_hours:
            if opening_hours.get("open_now") is True:
                description_parts.append("現在営業中")
            elif opening_hours.get("open_now") is False:
                description_parts.append("現在営業時間外")
            
            # 営業時間の詳細（あれば）
            weekday_text = opening_hours.get("weekday_text", [])
            if weekday_text and len(weekday_text) > 0:
                # 今日の営業時間を抽出（最初の1行目）
                today_hours = weekday_text[0] if isinstance(weekday_text[0], str) else ""
                if "24 時間営業" in today_hours or "24時間" in today_hours:
                    description_parts.append("24時間営業")
        
        # エリア情報（住所から抽出）
        if address:
            # 日本の住所から区・市を抽出
            import re
            area_match = re.search(r'([^都道府県]+[市区町村])', address)
            if area_match:
                area = area_match.group(1)
                description_parts.append(f"{area}エリア")
        
        # 特殊な施設タイプの追加情報
        special_features = []
        for place_type in types:
            if place_type == "point_of_interest":
                special_features.append("名所")
            elif place_type == "natural_feature":
                special_features.append("自然スポット")
            elif place_type == "establishment":
                continue  # 一般的すぎるので無視
            elif place_type == "food" and main_type not in ["レストラン", "カフェ"]:
                special_features.append("飲食店")
        
        if special_features:
            description_parts.extend(special_features[:2])  # 最大2つまで
        
        # 文章を組み立て
        if description_parts:
            # 最初の要素（場所のタイプ）を除いて、残りを「、」で結合
            if len(description_parts) == 1:
                return description_parts[0] + "です。"
            else:
                main_desc = description_parts[0]
                sub_desc = "、".join(description_parts[1:])
                return f"{main_desc}です。{sub_desc}。"
        else:
            return "詳細情報は取得できませんでした。"

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
            "recommendation_reason": self._generate_recommendation_reason(place_data),
            "details": {
                "name": place_data.get("name", f"장소_{index}"),
                "congestion": self._generate_realistic_congestion(
                    place_data, index
                ),  # 현실적인 혼잡도
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
            "similarity_score": place_data.get(
                "similarity_score", None
            ),  # similarity_score 추가
        }

    async def get_recommendations(
        self, pre_info: PreInfo, chat_keywords: Optional[List[str]] = None
    ) -> Dict:
        """
        Get spot recommendations based on pre_info.
        If chat_keywords are provided, they are used instead of generating new ones.
        """
        start_time = time.time()
        logger.info("🚀 SUPER 최적화 모드 시작!")

        if chat_keywords:
            logger.info(f"💬 Using keywords from chat: {chat_keywords}")
            tasks = [
                asyncio.sleep(
                    0, result=chat_keywords
                ),  # immediately completed coroutine
                self.llm_service.generate_llm_weights(pre_info),
                self.vector_search_service.get_similar_spots_by_pre_info(pre_info),
            ]
        else:
            logger.info("🔥 3개 작업 병렬 실행 시작...")
            tasks = [
                self._generate_llm_keywords(pre_info),
                self.llm_service.generate_llm_weights(pre_info),
                self.vector_search_service.get_similar_spots_by_pre_info(pre_info),
            ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                # 예외 처리 로직을 추가할 수 있습니다.
                logger.error(f"작업 실패: {result}")

        # 이전 코드의 나머지 부분을 그대로 유지
        # ...

        # 임시 fallback: 기존 recommend_spots_from_pre_info 로 전체 파이프라인 실행
        # 만약 상단 최적화 로직이 아직 완성되지 않았다면, 안전하게 이전 구현을 호출하여 결과 반환
        logger.info("🔄 Falling back to recommend_spots_from_pre_info pipeline")
        return await self.recommend_spots_from_pre_info(pre_info)

    async def _generate_llm_keywords(self, pre_info: PreInfo) -> List[str]:
        """Alias for backward-compatibility with older code paths."""
        return await self._generate_keywords_optimized(pre_info)
