import asyncio
import numpy as np
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import os
from datetime import datetime

from app.models.pre_info import PreInfo


class VectorSearchService:
    """
    Vector Search サービス
    ユーザー旅行情報と場所情報の意味類似度を計算してフィルタリング
    """

    def __init__(self):
        try:
            print("🎯 VectorSearchService初期化開始...")

            # Sentence Transformer モデル初期化
            # 多言語対応モデル使用 (日本語・韓国語・英語サポート)
            model_name = "paraphrase-multilingual-MiniLM-L12-v2"
            print(f"📡 Sentence Transformerモデル読み込み中: {model_name}")

            self.model = SentenceTransformer(model_name)
            print("✅ VectorSearchService初期化完了")

        except Exception as e:
            print(f"❌ VectorSearchService初期化失敗: {str(e)}")
            self.model = None

    async def find_similar_places(
        self, pre_info: PreInfo, places: List[Dict[str, Any]], limit: int = 80
    ) -> List[Dict[str, Any]]:
        """
        ユーザー旅行情報と類似度の高い場所を選別

        Args:
            pre_info: ユーザー旅行情報
            places: 場所詳細リスト
            limit: 返却する最大場所数

        Returns:
            類似度順でソートされた場所リスト
        """
        if not self.model or not places:
            print("⚠️ VectorSearchService利用不可またはデータなし。フォールバック使用")
            return places[:limit]

        try:
            print(f"🎯 Vector Search開始: {len(places)}個から{limit}個選別")

            # Step 1: ユーザー旅行情報からクエリテキスト生成
            user_query = self._create_user_query(pre_info)
            print(f"📝 ユーザークエリ: {user_query}")

            # Step 2: 各場所の説明テキスト生成
            place_texts = []
            for place in places:
                place_text = self._create_place_text(place)
                place_texts.append(place_text)

            print(f"🏗️ 場所テキスト生成完了: {len(place_texts)}個")

            # Step 3: 埋め込みベクトル生成 (並列処理対応)
            user_embedding = await self._get_embedding(user_query)
            place_embeddings = await self._get_embeddings_batch(place_texts)

            # Step 4: 類似度計算
            similarities = []
            for i, place_embedding in enumerate(place_embeddings):
                similarity = self._cosine_similarity(user_embedding, place_embedding)
                similarities.append((i, similarity))

            # Step 5: 類似度順でソート
            similarities.sort(key=lambda x: x[1], reverse=True)

            # Step 6: 上位limit個選択
            selected_places = []
            for i, (place_idx, similarity) in enumerate(similarities[:limit]):
                place = places[place_idx].copy()
                place["similarity_score"] = float(
                    similarity
                )  # numpy float -> Python float
                place["similarity_rank"] = i + 1
                selected_places.append(place)

            print(f"✅ Vector Search完了: {len(selected_places)}個選別")
            top_scores = [p.get("similarity_score", 0) for p in selected_places[:5]]
            print(f"🏆 トップ5類似度: {[f'{score:.3f}' for score in top_scores]}")

            return selected_places

        except Exception as e:
            print(f"❌ Vector Search失敗: {str(e)}")
            print("🔄 フォールバック: 元のリスト返却")
            return places[:limit]

    def _create_user_query(self, pre_info: PreInfo) -> str:
        """
        ユーザー旅行情報から検索クエリテキスト生成
        """
        parts = []

        # 地域情報
        if pre_info.region:
            parts.append(f"地域: {pre_info.region}")

        # 予算情報
        if pre_info.budget_per_person:
            budget_text = f"予算: {pre_info.budget_per_person:,}円"
            if pre_info.budget_per_person <= 50000:
                budget_text += " (節約志向)"
            elif pre_info.budget_per_person >= 100000:
                budget_text += " (高級志向)"
            parts.append(budget_text)

        # 人数情報
        if pre_info.participants_count:
            group_type = ""
            if pre_info.participants_count == 1:
                group_type = "一人旅"
            elif pre_info.participants_count == 2:
                group_type = "カップル旅行"
            elif pre_info.participants_count <= 4:
                group_type = "小グループ旅行"
            else:
                group_type = "大グループ旅行"
            parts.append(f"人数: {pre_info.participants_count}人 ({group_type})")

        # 期間情報
        if pre_info.start_date and pre_info.end_date:
            import datetime

            start = datetime.datetime.fromisoformat(
                pre_info.start_date.replace("Z", "+00:00")
            )
            end = datetime.datetime.fromisoformat(
                pre_info.end_date.replace("Z", "+00:00")
            )
            duration = (end - start).days + 1
            parts.append(f"期間: {duration}日間")

        query = " ".join(parts)
        return query

    def _create_place_text(self, place: Dict[str, Any]) -> str:
        """
        場所情報から説明テキスト生成
        """
        parts = []

        # 名前
        if place.get("name"):
            parts.append(f"名前: {place['name']}")

        # 住所
        if place.get("address"):
            parts.append(f"住所: {place['address']}")

        # 評価
        if place.get("rating"):
            rating_text = f"評価: {place['rating']}点"
            if place.get("ratings_total"):
                rating_text += f" ({place['ratings_total']}件)"
            parts.append(rating_text)

        # 価格レベル
        if place.get("price_level"):
            price_levels = {1: "格安", 2: "リーズナブル", 3: "中級", 4: "高級"}
            price_text = price_levels.get(place["price_level"], "価格不明")
            parts.append(f"価格帯: {price_text}")

        # カテゴリ
        if place.get("types") and isinstance(place["types"], list):
            # Google Places APIのタイプを日本語に変換
            type_translations = {
                "restaurant": "レストラン",
                "tourist_attraction": "観光地",
                "lodging": "宿泊施設",
                "shopping_mall": "ショッピングモール",
                "museum": "博物館",
                "park": "公園",
                "cafe": "カフェ",
                "bar": "バー",
                "establishment": "施設",
            }

            translated_types = []
            for place_type in place["types"][:3]:  # 最大3個まで
                translated = type_translations.get(place_type, place_type)
                translated_types.append(translated)

            if translated_types:
                parts.append(f"カテゴリ: {', '.join(translated_types)}")

        text = " ".join(parts)
        return text

    async def _get_embedding(self, text: str) -> np.ndarray:
        """
        単一テキストの埋め込みベクトル取得
        """
        if not self.model:
            # フォールバック: ランダムベクトル
            return np.random.rand(384)  # MiniLM-L12-v2の次元数

        try:
            # 非同期処理対応 (CPU集約的なので別スレッドで実行)
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, lambda: self.model.encode([text], convert_to_numpy=True)[0]
            )
            return embedding

        except Exception as e:
            print(f"❌ 埋め込み生成失敗: {str(e)}")
            return np.random.rand(384)

    async def _get_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        複数テキストの埋め込みベクトル一括取得
        """
        if not self.model:
            # フォールバック: ランダムベクトル
            return [np.random.rand(384) for _ in texts]

        try:
            # バッチ処理で効率化
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self.model.encode(
                    texts, convert_to_numpy=True, show_progress_bar=False
                ),
            )
            return list(embeddings)

        except Exception as e:
            print(f"❌ バッチ埋め込み生成失敗: {str(e)}")
            return [np.random.rand(384) for _ in texts]

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        コサイン類似度計算
        """
        try:
            # ベクトル正規化
            vec1_norm = vec1 / np.linalg.norm(vec1)
            vec2_norm = vec2 / np.linalg.norm(vec2)

            # コサイン類似度
            similarity = np.dot(vec1_norm, vec2_norm)

            # -1 ~ 1 の範囲を 0 ~ 1 に変換
            similarity = (similarity + 1) / 2

            return float(similarity)

        except Exception as e:
            print(f"❌ 類似度計算失敗: {str(e)}")
            return 0.5  # 中立値
