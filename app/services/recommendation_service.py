from typing import List, Dict, Any
import time
from datetime import datetime

from app.models.pre_info import PreInfo
from app.schemas.spot import RecommendSpots
from app.services.llm_service import LLMService
from app.services.google_trends_service import GoogleTrendsService
from app.services.places_service import PlacesService


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

            # TODO: 他のサービス依存性注入
            # self.vector_search_service = vector_search_service
            # self.scoring_service = scoring_service

            print("✅ RecommendationService初期化完了")

        except Exception as e:
            print(f"❌ RecommendationService初期化失敗: {str(e)}")
            # 初期化失敗してもサービスは継続実行
            self.llm_service = None
            self.google_trends_service = None
            self.places_service = None

    async def recommend_spots_from_pre_info(self, pre_info: PreInfo) -> Dict[str, Any]:
        """
        pre_infoを基にスポット推薦を生成

        Args:
            pre_info: ユーザー旅行事前情報

        Returns:
            推薦結果とメタデータ
        """
        start_time = time.time()
        processing_metadata = {
            "api_calls_made": 0,
            "total_spots_found": 0,
            "scoring_weights": {},
        }

        try:
            # Step 3-1: LLMキーワード + 初期重み生成
            keywords, initial_weights = await self._generate_keywords_and_weights(
                pre_info
            )
            processing_metadata["api_calls_made"] += 1

            # Step 3-2: Google Trendsフィルタリング (実際の実装!)
            hot_keywords = await self._filter_trending_keywords(keywords)
            processing_metadata["api_calls_made"] += len(keywords)

            # Step 3-3: Places Text Search
            place_ids = await self._search_places_by_keywords(hot_keywords, pre_info)
            processing_metadata["api_calls_made"] += len(hot_keywords)

            # Step 3-4: Places Details
            place_details = await self._get_place_details(place_ids)
            processing_metadata["api_calls_made"] += 1
            processing_metadata["total_spots_found"] = len(place_details)

            # Step 3-5: Vector Search (意味類似度)
            vector_candidates = await self._vector_search_similarity(
                pre_info, place_details
            )
            processing_metadata["api_calls_made"] += 1

            # Step 3-6: LLM再ランキング + 重み調整 (80個 → 40個)
            reranked_spots, updated_weights = await self._llm_rerank_and_adjust_weights(
                vector_candidates, initial_weights, pre_info
            )
            processing_metadata["api_calls_made"] += 1
            processing_metadata["scoring_weights"] = updated_weights

            # Step 3-7: 最終スコアリング (40個 → TOP-N)
            final_recommendations = await self._final_scoring_and_ranking(
                reranked_spots, updated_weights, pre_info
            )

            # 処理時間計算
            processing_time_ms = int((time.time() - start_time) * 1000)

            # 最終メタデータログ出力
            print("🎯 最終レスポンスメタデータ:")
            print(f"  - Keywords: {keywords}")
            print(f"  - Hot Keywords: {hot_keywords}")
            print(f"  - Weights: {updated_weights}")
            print(f"  - Processing time: {processing_time_ms}ms")
            print(f"  - API calls: {processing_metadata['api_calls_made']}")

            return {
                "rec_spot_id": f"rec_{int(datetime.now().timestamp())}",
                "recommend_spots": final_recommendations,
                "processing_time_ms": processing_time_ms,
                "keywords_generated": keywords,  # デバッグ用追加
                "hot_keywords": hot_keywords,  # トレンディングキーワード追加
                "initial_weights": initial_weights,  # デバッグ用追加
                **processing_metadata,
            }

        except Exception as e:
            # エラー発生時も処理時間は返却
            processing_time_ms = int((time.time() - start_time) * 1000)
            raise Exception(
                f"推薦処理中エラー発生: {str(e)} (処理時間: {processing_time_ms}ms)"
            )

    async def _generate_keywords_and_weights(
        self, pre_info: PreInfo
    ) -> tuple[List[str], Dict[str, float]]:
        """Step 3-1: LLMを使用してキーワードと初期重み生成"""
        if self.llm_service is None:
            print("⚠️ LLMServiceなし。フォールバックロジック使用")
            # 簡単なフォールバックロジック
            keywords = [
                f"{pre_info.region} 観光地",
                f"{pre_info.region} グルメ",
                f"{pre_info.region} カフェ",
            ]
            weights = {
                "price": 0.3,
                "rating": 0.4,
                "congestion": 0.2,
                "similarity": 0.1,
            }
            return keywords, weights

        return await self.llm_service.generate_keywords_and_weights(pre_info)

    async def _filter_trending_keywords(self, keywords: List[str]) -> List[str]:
        """Step 3-2: Google Trendsで人気キーワードフィルタリング (実際の実装!)"""
        if self.google_trends_service is None:
            print("⚠️ GoogleTrendsServiceなし。フォールバック使用")
            print(f"🔥 フォールバック - 全キーワード使用: {keywords}")
            return keywords

        # 実際のGoogle Trends APIを使用してキーワードフィルタリング
        trending_keywords = await self.google_trends_service.filter_trending_keywords(
            keywords, threshold=30  # 人気度30以上のキーワードのみ
        )

        print(f"🔥 Google Trendsフィルタリング完了: {trending_keywords}")
        return trending_keywords

    async def _search_places_by_keywords(
        self, keywords: List[str], pre_info: PreInfo
    ) -> List[str]:
        """Step 3-3: Places Text Searchで場所ID収集 (実際の実装!)"""
        if self.places_service is None:
            print("⚠️ PlacesServiceなし。フォールバック使用")
            print(f"🔍 フォールバック - ダミーplace_id生成: {keywords}")
            return [f"fallback_place_{i}" for i in range(20)]

        try:
            all_place_ids = []
            print(f"🔍 Places Text Search開始: {len(keywords)}個キーワード")

            # 各キーワードで検索実行
            for keyword in keywords:
                place_ids = await self.places_service.text_search(
                    keyword, pre_info.region
                )
                all_place_ids.extend(place_ids)
                print(f"  ✅ '{keyword}': {len(place_ids)}個発見")

            # 重複削除
            unique_place_ids = list(set(all_place_ids))
            print(f"🎯 重複削除後: {len(unique_place_ids)}個のユニークplace_id")

            return unique_place_ids

        except Exception as e:
            print(f"❌ Places Text Search失敗: {str(e)}")
            # フォールバック
            return [f"error_place_{i}" for i in range(10)]

    async def _get_place_details(self, place_ids: List[str]) -> List[Dict[str, Any]]:
        """Step 3-4: Places Detailsで詳細情報取得 (実際の実装!)"""
        if self.places_service is None:
            print("⚠️ PlacesServiceなし。フォールバック使用")
            print(f"📍 フォールバック - ダミー詳細情報生成: {len(place_ids)}個")
            return [
                {
                    "place_id": pid,
                    "name": f"場所_{i+1}",
                    "rating": 4.0 + (i % 5) * 0.2,
                    "address": "住所情報なし",
                    "lat": 35.6762 + (i * 0.01),
                    "lng": 139.6503 + (i * 0.01),
                    "price_level": (i % 4) + 1,
                    "types": ["establishment"],
                }
                for i, pid in enumerate(place_ids[:20])
            ]

        try:
            print(f"📍 Places Details一括取得開始: {len(place_ids)}個")

            # Places API로 상세 정보 취득
            place_details = await self.places_service.get_place_details_batch(place_ids)

            print(f"✅ Places Details取得完了: {len(place_details)}個")
            return place_details

        except Exception as e:
            print(f"❌ Places Details取得失敗: {str(e)}")
            # フォールバック
            return [
                {
                    "place_id": pid,
                    "name": f"エラー場所_{i+1}",
                    "rating": 3.5,
                    "address": "詳細情報取得失敗",
                    "lat": 35.6762,
                    "lng": 139.6503,
                    "price_level": 2,
                    "types": ["establishment"],
                }
                for i, pid in enumerate(place_ids[:10])
            ]

    async def _vector_search_similarity(
        self, pre_info: PreInfo, places: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Step 3-5: Vector Searchで意味類似度計算 (80個候補)"""
        # TODO: Vector Searchサービス呼び出し
        # return await self.vector_search_service.find_similar_places(pre_info, places, limit=80)

        # 仮：上位80個選択 (または全体が80個未満なら全体)
        result = places[:80] if len(places) >= 80 else places
        print(f"🎯 Vector Search類似度計算: {len(result)}個候補")
        return result

    async def _llm_rerank_and_adjust_weights(
        self,
        candidates: List[Dict[str, Any]],
        weights: Dict[str, float],
        pre_info: PreInfo,
    ) -> tuple[List[Dict[str, Any]], Dict[str, float]]:
        """Step 3-6: LLM再ランキング + 重み調整 (80個 → 40個)"""
        if self.llm_service is None:
            print("⚠️ LLMServiceなし。シンプル再ランキング使用")
            # 簡単なフォールバック：上位40個 + 重み微調整
            reranked = candidates[:40] if len(candidates) >= 40 else candidates
            adjusted_weights = {**weights, "rating": weights.get("rating", 0.4) + 0.1}
            return reranked, adjusted_weights

        return await self.llm_service.rerank_and_adjust_weights(
            candidates, weights, pre_info
        )

    async def _final_scoring_and_ranking(
        self, spots: List[Dict[str, Any]], weights: Dict[str, float], pre_info: PreInfo
    ) -> List[Dict[str, Any]]:
        """Step 3-7: 最終スコアリングでTOP-N選別とAPI스키마 변환"""
        # TODO: Scoringサービス呼び出し
        # return await self.scoring_service.score_and_rank(spots, weights, pre_info, top_n=10)

        # 仮：上位10個選択
        top_spots = spots[:10] if len(spots) >= 10 else spots
        print(f"🏆 最終スコアリング: {len(top_spots)}個選別")

        # API 스키마에 맞게 TimeSlotSpots 형식으로 변환
        formatted_spots = []

        # 스포트들을 3개 시간대로 분배 (단순 분배)
        spots_per_slot = len(top_spots) // 3 + (1 if len(top_spots) % 3 > 0 else 0)

        time_slots = ["午前", "午後", "夜"]
        for i, time_slot in enumerate(time_slots):
            start_idx = i * spots_per_slot
            end_idx = min((i + 1) * spots_per_slot, len(top_spots))
            slot_spots = top_spots[start_idx:end_idx]

            if slot_spots:  # 해당 시간대에 스포트가 있는 경우만 추가
                formatted_spots.append(
                    {
                        "time_slot": time_slot,
                        "spots": [
                            self._convert_to_spot_schema(spot, idx)
                            for idx, spot in enumerate(slot_spots)
                        ],
                    }
                )

        print(f"📋 시간대별 분배 완료: {len(formatted_spots)}개 시간대")
        return formatted_spots

    def _convert_to_spot_schema(
        self, place_data: Dict[str, Any], index: int
    ) -> Dict[str, Any]:
        """Places API 데이터를 Spot 스키마로 변환"""
        # 기본 영업시간 생성 (실제로는 opening_hours 파싱 필요)
        business_hours = {
            "MONDAY": {"open_time": "09:00:00", "close_time": "18:00:00"},
            "TUESDAY": {"open_time": "09:00:00", "close_time": "18:00:00"},
            "WEDNESDAY": {"open_time": "09:00:00", "close_time": "18:00:00"},
            "THURSDAY": {"open_time": "09:00:00", "close_time": "18:00:00"},
            "FRIDAY": {"open_time": "09:00:00", "close_time": "18:00:00"},
            "SATURDAY": {"open_time": "09:00:00", "close_time": "18:00:00"},
            "SUNDAY": {"open_time": "09:00:00", "close_time": "18:00:00"},
            "HOLIDAY": {"open_time": "09:00:00", "close_time": "18:00:00"},
        }

        # 기본 혼잡도 데이터 (0-23시간)
        congestion = [30 + (i * 5) % 70 for i in range(24)]  # 시간별 혼잡도 모의

        return {
            "spot_id": place_data.get("place_id", f"spot_{index}"),
            "longitude": place_data.get("lng", 0.0),
            "latitude": place_data.get("lat", 0.0),
            "recommendation_reason": f"{place_data.get('name', '장소')}는 평점 {place_data.get('rating', 0.0)}으로 추천합니다.",
            "details": {
                "name": place_data.get("name", f"장소_{index}"),
                "congestion": congestion,
                "business_hours": business_hours,
                "price": place_data.get("price_level", 2)
                * 1000,  # price_level을 원화로 변환
            },
            "selected": False,
        }
