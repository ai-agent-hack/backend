from typing import List, Dict, Any
import time
from datetime import datetime

from app.models.pre_info import PreInfo
from app.schemas.spot import RecommendSpots
from app.services.llm_service import LLMService
from app.services.google_trends_service import GoogleTrendsService


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

            # TODO: 他のサービス依存性注入
            # self.places_service = places_service
            # self.vector_search_service = vector_search_service
            # self.scoring_service = scoring_service

            print("✅ RecommendationService初期化完了")

        except Exception as e:
            print(f"❌ RecommendationService初期化失敗: {str(e)}")
            # 初期化失敗してもサービスは継続実行
            self.llm_service = None
            self.google_trends_service = None

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
        """Step 3-3: Places Text Searchで場所ID収集"""
        # TODO: Placesサービス呼び出し
        # place_ids = []
        # for keyword in keywords:
        #     ids = await self.places_service.text_search(keyword, pre_info.region)
        #     place_ids.extend(ids)
        # return place_ids

        # 仮ダミーデータ
        print(f"🔍 Places検索キーワード: {keywords}")
        return [f"place_id_{i}" for i in range(20)]

    async def _get_place_details(self, place_ids: List[str]) -> List[Dict[str, Any]]:
        """Step 3-4: Places Detailsで詳細情報取得"""
        # TODO: Placesサービス呼び出し
        # return await self.places_service.get_place_details_batch(place_ids)

        # 仮ダミーデータ
        print(f"📍 Places詳細情報照会: {len(place_ids)}個")
        return [
            {"place_id": pid, "name": f"場所_{pid}", "rating": 4.5} for pid in place_ids
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
        """Step 3-7: 最終スコアリングでTOP-N選別"""
        # TODO: Scoringサービス呼び出し
        # return await self.scoring_service.score_and_rank(spots, weights, pre_info, top_n=10)

        # 仮：上位10個選択
        result = spots[:10] if len(spots) >= 10 else spots
        print(f"🏆 最終スコアリング: {len(result)}個選別")
        return result
