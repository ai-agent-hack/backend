from typing import List, Dict, Any
import math
from datetime import datetime

from app.models.pre_info import PreInfo


class ScoringService:
    """
    Scoring Service
    多次元重み付けでスポットの最終スコアリングを実行
    """

    def __init__(self):
        print("🏆 ScoringService初期化完了")

    async def score_and_rank(
        self,
        spots: List[Dict[str, Any]],
        weights: Dict[str, float],
        pre_info: PreInfo,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Step 3-7: 最終スコアリングとランキング (40個 → TOP-N)

        Args:
            spots: 40個スポットリスト
            weights: 調整された重み
            pre_info: ユーザー旅行情報
            top_n: 返却する上位個数 (デフォルト10個)

        Returns:
            スコア順でソートされたスポットリスト
        """
        try:
            print(f"🏆 最終スコアリング開始: {len(spots)}個 → TOP-{top_n}")
            print(f"⚖️ 使用重み: {weights}")

            scored_spots = []

            for spot in spots:
                # 多次元スコア計算
                scores = self._calculate_multi_dimensional_scores(spot, pre_info)

                # 重み付け最終スコア計算
                final_score = self._calculate_weighted_score(scores, weights)

                # スポットにスコア情報追加
                spot_with_score = spot.copy()
                spot_with_score.update(
                    {
                        "final_score": final_score,
                        "score_breakdown": scores,
                        "weights_used": weights.copy(),
                    }
                )

                scored_spots.append(spot_with_score)

            # スコア順でソート (降順)
            scored_spots.sort(key=lambda x: x["final_score"], reverse=True)

            # TOP-N選択
            top_spots = scored_spots[:top_n]

            print(f"✅ 最終スコアリング完了: TOP-{len(top_spots)}個選別")
            print(
                f"🥇 最高スコア: {top_spots[0]['final_score']:.3f}" if top_spots else ""
            )

            return top_spots

        except Exception as e:
            print(f"❌ 最終スコアリング失敗: {str(e)}")
            # フォールバックとして上位N個返却
            return spots[:top_n]

    def _calculate_multi_dimensional_scores(
        self, spot: Dict[str, Any], pre_info: PreInfo
    ) -> Dict[str, float]:
        """
        多次元スコア計算 (price, rating, congestion, similarity)
        """
        scores = {}

        # 1. Price Score (価格スコア)
        scores["price"] = self._calculate_price_score(spot, pre_info)

        # 2. Rating Score (評点スコア)
        scores["rating"] = self._calculate_rating_score(spot)

        # 3. Congestion Score (混雑度スコア)
        scores["congestion"] = self._calculate_congestion_score(spot, pre_info)

        # 4. Similarity Score (類似度スコア)
        scores["similarity"] = self._calculate_similarity_score(spot)

        return scores

    def _calculate_price_score(self, spot: Dict[str, Any], pre_info: PreInfo) -> float:
        """
        価格スコア計算 (ユーザー予算との適合度)
        """
        try:
            price_level = spot.get("price_level", 2)  # デフォルト中級
            user_budget = pre_info.budget

            # price_levelを想定価格に変換 (1=格安, 2=中級, 3=高級, 4=最高級)
            price_ranges = {
                1: (0, 30000),  # 格安: ~3万円
                2: (20000, 80000),  # 中級: 2~8万円
                3: (60000, 150000),  # 高級: 6~15万円
                4: (120000, 300000),  # 最高級: 12~30万円
            }

            min_price, max_price = price_ranges.get(price_level, (20000, 80000))
            avg_price = (min_price + max_price) / 2

            # 予算適合度計算 (予算に近いほど高スコア)
            if user_budget >= avg_price:
                # 予算内 → 高スコア
                score = min(1.0, user_budget / avg_price * 0.8)
            else:
                # 予算超過 → 低スコア
                score = user_budget / avg_price

            return max(0.0, min(1.0, score))

        except Exception as e:
            print(f"❌ 価格スコア計算失敗: {str(e)}")
            return 0.5  # 中立値

    def _calculate_rating_score(self, spot: Dict[str, Any]) -> float:
        """
        評点スコア計算 (Google評価基準)
        """
        try:
            rating = spot.get("rating", 0.0)
            ratings_total = spot.get("ratings_total", 0)

            if rating <= 0:
                return 0.3  # 評価なしは低スコア

            # 基本評価スコア (5点満点を1点満点に正規化)
            base_score = rating / 5.0

            # 評価数ボーナス (信頼性向上)
            if ratings_total >= 1000:
                reliability_bonus = 0.2
            elif ratings_total >= 100:
                reliability_bonus = 0.1
            elif ratings_total >= 10:
                reliability_bonus = 0.05
            else:
                reliability_bonus = 0.0

            final_score = base_score + reliability_bonus
            return max(0.0, min(1.0, final_score))

        except Exception as e:
            print(f"❌ 評点スコア計算失敗: {str(e)}")
            return 0.5

    def _calculate_congestion_score(
        self, spot: Dict[str, Any], pre_info: PreInfo
    ) -> float:
        """
        混雑度スコア計算 (雰囲気との適合度)
        """
        try:
            # TODO: 実際の混雑度データがある場合はそれを使用
            # 現在は雰囲気基準で仮想混雑度スコア算出

            atmosphere = getattr(pre_info, "atmosphere", "普通")

            # 評価数を混雑度指標として活用
            ratings_total = spot.get("ratings_total", 0)

            # 人気度レベル算出 (評価数基準)
            if ratings_total >= 1000:
                popularity = 1.0  # 非常に人気
            elif ratings_total >= 500:
                popularity = 0.8  # 人気
            elif ratings_total >= 100:
                popularity = 0.6  # 普通
            elif ratings_total >= 50:
                popularity = 0.4  # 静か
            else:
                popularity = 0.2  # 非常に静か

            # 雰囲気と混雑度のマッチング
            atmosphere_preferences = {
                "静か": 0.2,  # 静かな雰囲気 → 低い人気度を好む
                "普通": 0.6,  # 普通の雰囲気 → 普通の人気度を好む
                "活気": 1.0,  # 活気ある雰囲気 → 高い人気度を好む
                "ロマンチック": 0.4,  # ロマンチックな雰囲気 → 適度な人気度を好む
            }

            preferred_popularity = atmosphere_preferences.get(atmosphere, 0.6)

            # 好みと実際の人気度の差でスコア計算
            difference = abs(popularity - preferred_popularity)
            score = 1.0 - difference  # 差が小さいほど高いスコア

            return max(0.0, min(1.0, score))

        except Exception as e:
            print(f"❌ 混雑度スコア計算失敗: {str(e)}")
            return 0.5

    def _calculate_similarity_score(self, spot: Dict[str, Any]) -> float:
        """
        類似度スコア計算 (Vector Searchから受け継ぎ)
        """
        try:
            # Vector Searchで計算された類似度スコア使用
            similarity_score = spot.get("similarity_score")

            if similarity_score is not None:
                return max(0.0, min(1.0, float(similarity_score)))
            else:
                # Vector Searchスコアがない場合の基本値
                return 0.5

        except Exception as e:
            print(f"❌ 類似度スコア計算失敗: {str(e)}")
            return 0.5

    def _calculate_weighted_score(
        self, scores: Dict[str, float], weights: Dict[str, float]
    ) -> float:
        """
        重み付け最終スコア計算
        """
        try:
            final_score = 0.0
            total_weight = 0.0

            for dimension, score in scores.items():
                weight = weights.get(dimension, 0.0)

                # 型安全性を確保
                try:
                    score_float = float(score)
                    weight_float = float(weight)
                except (ValueError, TypeError):
                    score_float = 0.5
                    weight_float = 0.1

                final_score += score_float * weight_float
                total_weight += weight_float

            # 重み正規化 (合計が1.0でない場合に対応)
            if total_weight > 0:
                final_score = final_score / total_weight
            else:
                final_score = 0.5

            return max(0.0, min(1.0, final_score))

        except Exception as e:
            print(f"❌ 重み付けスコア計算失敗: {str(e)}")
            return 0.5
