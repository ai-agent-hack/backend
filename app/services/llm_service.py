import json
import os
from typing import List, Dict, Any, Tuple
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

from app.models.pre_info import PreInfo
from app.core.config import settings


class LLMService:
    """
    LLM サービス - Vertex AI Gemini を使用
    """

    def __init__(self):
        self.model = None
        self._initialize_vertex_ai()

    def _initialize_vertex_ai(self):
        """Vertex AI 初期化"""
        try:
            project_id = os.getenv("GOOGLE_PROJECT_ID") or os.getenv(
                "GOOGLE_CLOUD_PROJECT"
            )
            if not project_id:
                raise Exception("GOOGLE_PROJECT_ID環境変数が設定されていません")

            # 認証情報の取得
            credentials = self._get_vertex_credentials()

            # Vertex AI 初期化
            if credentials:
                vertexai.init(
                    project=project_id, location="us-central1", credentials=credentials
                )
            else:
                vertexai.init(project=project_id, location="us-central1")

            # Gemini モデル設定
            self.model = GenerativeModel("gemini-2.0-flash")
            print("✅ Vertex AI Gemini モデル初期化完了")

        except Exception as e:
            print(f"❌ Vertex AI 初期化失敗: {str(e)}")
            self.model = None

    def _get_vertex_credentials(self):
        """Google Cloud 認証情報取得"""
        try:
            service_account_data = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if service_account_data:
                # JSON文字列の場合
                if service_account_data.strip().startswith("{"):
                    credentials_info = json.loads(service_account_data)
                    credentials = service_account.Credentials.from_service_account_info(
                        credentials_info
                    )
                    return credentials
                # ファイルパスの場合
                elif os.path.exists(service_account_data):
                    credentials = service_account.Credentials.from_service_account_file(
                        service_account_data
                    )
                    return credentials
            return None
        except Exception as e:
            print(f"❌ 認証情報ロード失敗: {str(e)}")
            return None

    async def generate_keywords_and_weights(
        self, pre_info: PreInfo
    ) -> Tuple[List[str], Dict[str, float]]:
        """
        Step 3-1: pre_infoを基に検索キーワードと初期重みを生成

        Args:
            pre_info: ユーザー旅行事前情報

        Returns:
            tuple: (キーワードリスト, 重み辞書)
        """
        if not self.model:
            print("⚠️ Vertex AI モデルがありません。フォールバックロジック使用")
            return self._get_fallback_keywords_and_weights(pre_info)

        try:
            prompt = self._create_keyword_generation_prompt(pre_info)

            generation_config = GenerationConfig(
                temperature=0.7,  # 創造性と一貫性のバランス
                top_p=0.9,
                max_output_tokens=1024,
                response_mime_type="application/json",  # JSON形式で応答要求
            )

            print(
                f"🤖 LLMにキーワード生成要請中... (地域: {pre_info.region}, 予算: {pre_info.budget:,}円, 雰囲気: {pre_info.atmosphere})"
            )
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
            )

            # JSON応答パース
            result = json.loads(response.text)
            keywords = result.get("keywords", [])
            weights = result.get("weights", {})

            # 重み値をfloatに変換 (LLMが文字列で返す可能性)
            converted_weights = {}
            for key, value in weights.items():
                try:
                    converted_weights[key] = float(value)
                except (ValueError, TypeError):
                    converted_weights[key] = 0.1  # デフォルト値

            # 有効性検証
            if not keywords or not converted_weights:
                raise Exception("LLM応答にキーワードまたは重みがありません")

            print(f"✅ LLMキーワード生成成功: {keywords}")
            print(f"✅ LLM重み生成: {converted_weights}")
            return keywords, converted_weights

        except Exception as e:
            print(f"❌ LLMキーワード生成失敗: {str(e)}")
            return self._get_fallback_keywords_and_weights(pre_info)

    def _create_keyword_generation_prompt(self, pre_info: PreInfo) -> str:
        """キーワード生成用プロンプト生成"""
        prompt = f"""
以下の旅行情報を分析して、スポット検索に使用するキーワードと推薦重みを生成してください。

**旅行情報:**
- 地域: {pre_info.region}  
- 旅行期間: {pre_info.start_date.strftime('%Y-%m-%d')} ~ {pre_info.end_date.strftime('%Y-%m-%d')}
- 予算: {pre_info.budget:,}円
- 雰囲気/好み: {pre_info.atmosphere}

**重要指示:**
1. **雰囲気/好み**を最優先に考慮してキーワードを生成してください
2. 予算と地域特性を反映した具体的なキーワード選択
3. 雰囲気に合った重み調整必須

**要求事項:**
1. 検索キーワード3-5個を生成:
   - 地域名 + 雰囲気関連キーワード組み合わせ
   - 具体的で検索可能な形式
   - 雰囲気を反映した特性キーワード含む
   
2. 推薦重みを0-1の値で設定:
   - price: 価格重要度 (予算が少ないほど高く)
   - rating: 評点重要度 
   - congestion: 混雑度重要度 (静かな雰囲気なら高く)
   - similarity: 意味的類似度重要度 (雰囲気マッチ度)

**雰囲気別キーワード生成例:**
- "静か/平和" → "静かなカフェ", "閑静な公園", "平和な庭園"
- "活気/賑やか" → "人気グルメ", "繁華街", "ショッピング街" 
- "ロマンチック" → "ロマンチックレストラン", "夜景スポット", "カップルカフェ"
- "家族向け" → "ファミリーレストラン", "子供の遊び場", "体験施設"

**応答形式 (JSON):**
{{
  "keywords": ["地域名 雰囲気キーワード1", "地域名 雰囲気キーワード2", "地域名 特性キーワード"],
  "weights": {{
    "price": 0.3,
    "rating": 0.4,
    "congestion": 0.2,
    "similarity": 0.1
  }},
  "atmosphere_analysis": "雰囲気分析およびキーワード選択理由"
}}

雰囲気 '{pre_info.atmosphere}' を核心として {pre_info.region} 地域の適切なキーワードと重みを設定してください。
"""
        return prompt

    def _get_fallback_keywords_and_weights(
        self, pre_info: PreInfo
    ) -> Tuple[List[str], Dict[str, float]]:
        """LLM失敗時に使用するデフォルトキーワードと重み"""
        print(
            f"🔄 フォールバックロジック使用 - 地域: {pre_info.region}, 予算: {pre_info.budget:,}円"
        )

        # 地域ベースのデフォルトキーワード
        region_keywords = {
            "ソウル": ["ソウル カフェ", "江南 グルメ", "漢江 公園"],
            "釜山": ["釜山 海岸", "広安里", "甘川文化村"],
            "済州": ["済州 自然", "漢拏山", "済州 カフェ"],
            "東京": ["東京 カフェ", "渋谷 グルメ", "浅草 観光"],
            "大阪": ["大阪 グルメ", "道頓堀", "大阪城"],
            "京都": ["京都 寺院", "嵐山", "清水寺"],
        }

        # 予算ベースの重み調整
        if pre_info.budget < 50000:
            weights = {
                "price": 0.5,
                "rating": 0.3,
                "congestion": 0.1,
                "similarity": 0.1,
            }
        elif pre_info.budget < 100000:
            weights = {
                "price": 0.3,
                "rating": 0.4,
                "congestion": 0.2,
                "similarity": 0.1,
            }
        else:
            weights = {
                "price": 0.2,
                "rating": 0.4,
                "congestion": 0.3,
                "similarity": 0.1,
            }

        # デフォルトキーワード選択
        keywords = region_keywords.get(
            pre_info.region,
            [
                f"{pre_info.region} 観光地",
                f"{pre_info.region} グルメ",
                f"{pre_info.region} カフェ",
            ],
        )

        print(f"📋 フォールバックキーワード: {keywords}")
        print(f"⚖️ フォールバック重み: {weights}")
        return keywords, weights

    async def rerank_and_adjust_weights(
        self,
        candidates: List[Dict[str, Any]],
        weights: Dict[str, float],
        pre_info: PreInfo,
        target_count: int = 40,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        """
        ステップ 3-6: LLM再ランキング + 重み調整（80個 → 40個）

        Args:
            candidates: 80個の候補場所リスト
            weights: 現在の重み
            pre_info: ユーザー旅行情報
            target_count: 選別する場所数（デフォルト40個）

        Returns:
            tuple: (再ランキングされた40個の場所, 調整された重み)
        """
        if not self.model:
            print("⚠️ Vertex AI モデルがありません。フォールバック使用")
            return self._fallback_reranking(candidates, weights, target_count)

        try:
            print(f"🤖 LLM再ランキング開始: {len(candidates)}個 → {target_count}個")

            # プロンプト生成
            prompt = self._create_rerank_prompt(
                candidates, weights, pre_info, target_count
            )

            generation_config = GenerationConfig(
                temperature=0.3,  # 一貫性重視
                top_p=0.8,
                max_output_tokens=2048,
                response_mime_type="application/json",
            )

            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
            )

            # JSON応答パース
            result = json.loads(response.text)

            # 選別された場所IDリスト
            selected_place_ids = result.get("selected_place_ids", [])
            adjusted_weights = result.get("adjusted_weights", weights)
            reasoning = result.get("reasoning", "再ランキング完了")

            # 重みをfloatに変換
            converted_weights = {}
            for key, value in adjusted_weights.items():
                try:
                    converted_weights[key] = float(value)
                except (ValueError, TypeError):
                    converted_weights[key] = weights.get(key, 0.25)  # デフォルト値使用

            # 選別された場所を順番に並べ替え
            reranked_places = []
            candidate_map = {
                place.get("place_id", place.get("name", "")): place
                for place in candidates
            }

            for place_id in selected_place_ids:
                if place_id in candidate_map:
                    place = candidate_map[place_id].copy()
                    place["llm_rank"] = len(reranked_places) + 1
                    place["llm_reasoning"] = reasoning
                    reranked_places.append(place)

                if len(reranked_places) >= target_count:
                    break

            # 不足している場合は残りの候補から補完
            if len(reranked_places) < target_count:
                remaining_count = target_count - len(reranked_places)
                used_ids = {
                    p.get("place_id", p.get("name", "")) for p in reranked_places
                }

                for place in candidates:
                    place_id = place.get("place_id", place.get("name", ""))
                    if place_id not in used_ids:
                        place_copy = place.copy()
                        place_copy["llm_rank"] = len(reranked_places) + 1
                        place_copy["llm_reasoning"] = "補完選択"
                        reranked_places.append(place_copy)

                        if len(reranked_places) >= target_count:
                            break

            print(f"✅ LLM再ランキング完了: {len(reranked_places)}個選別")
            print(f"🎯 調整された重み: {converted_weights}")
            print(f"💭 LLM判断: {reasoning[:100]}...")

            return reranked_places, converted_weights

        except Exception as e:
            print(f"❌ LLM再ランキング失敗: {str(e)}")
            return self._fallback_reranking(candidates, weights, target_count)

    def _create_rerank_prompt(
        self,
        candidates: List[Dict[str, Any]],
        weights: Dict[str, float],
        pre_info: PreInfo,
        target_count: int,
    ) -> str:
        """再ランキング用プロンプト生成"""

        # 候補場所を要約形式に変換
        candidate_summaries = []
        for i, place in enumerate(candidates[:80]):  # 最大80個まで
            summary = {
                "id": place.get("place_id", f"place_{i}"),
                "name": place.get("name", f"場所_{i}"),
                "rating": place.get("rating", 0.0),
                "price_level": place.get("price_level", 2),
                "address": place.get("address", "住所情報なし")[:50],  # 住所の長さ制限
                "types": place.get("types", [])[:3],  # タイプ数制限
                "similarity_score": place.get("similarity_score", 0.5),
            }
            candidate_summaries.append(summary)

        prompt = f"""
次は旅行推薦システムの場所再ランキング作業です。80個の候補からユーザーに最適な{target_count}個を選別してください。

**ユーザー旅行情報:**
- 地域: {pre_info.region}
- 予算: {pre_info.budget:,}円
- 人数: {pre_info.participants_count}名
- 雰囲気の好み: {pre_info.atmosphere}
- 期間: {pre_info.start_date} ~ {pre_info.end_date}

**現在の重み:**
{json.dumps(weights, indent=2, ensure_ascii=False)}

**候補場所（80個）:**
{json.dumps(candidate_summaries, indent=2, ensure_ascii=False)}

**作業要件:**

1. **パーソナライズフィルタリング**: ユーザーの予算、雰囲気、人数を考慮して不適合な場所を除外
   - 予算超過の場所をフィルタリング (price_level 4 = 高級, 3 = 中級, 2 = 普通, 1 = 安い)
   - 雰囲気に合わない場所を除外
   - グループサイズに不適合な場所を除外

2. **多様性の保証**: カテゴリ別バランスの維持
   - レストラン、観光地、文化施設、ショッピングなど多様なタイプを含む
   - 同一地域への集中を防止

3. **品質優先順位**: 
   - 評点4.0以上を優先選択
   - レビュー数が多い信頼できる場所を優先
   - ベクトル類似度スコアを考慮

4. **重み調整**: ユーザープロフィールに基づいて重みを微調整
   - 予算制約が強い場合 → price重みを増加
   - 雰囲気重視 → similarity, congestion重みを増加
   - 安全性重視 → rating重みを増加

**応答形式 (JSON):**
```json
{{
  "selected_place_ids": ["place_id_1", "place_id_2", ..., "place_id_{target_count}"],
  "adjusted_weights": {{
    "price": 0.35,
    "rating": 0.35,
    "congestion": 0.20,
    "similarity": 0.10
  }},
  "reasoning": "選別基準と重み調整の理由を2-3文で説明",
  "category_distribution": {{
    "restaurant": 12,
    "tourist_attraction": 8,
    "shopping": 5,
    "cultural": 6,
    "other": 9
  }}
}}
```

ユーザーの'{pre_info.atmosphere}'の雰囲気と予算{pre_info.budget:,}円を核心基準として最適な{target_count}個を選別してください。
"""
        return prompt

    def _fallback_reranking(
        self,
        candidates: List[Dict[str, Any]],
        weights: Dict[str, float],
        target_count: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        """LLM再ランキング失敗時のフォールバックロジック"""
        print(f"🔄 フォールバック再ランキング: {len(candidates)}個 → {target_count}個")

        # 評点基準でソート
        sorted_candidates = sorted(
            candidates,
            key=lambda x: (
                x.get("rating", 0.0) * 0.6 + x.get("similarity_score", 0.0) * 0.4
            ),
            reverse=True,
        )

        # 上位target_count個を選択
        selected = sorted_candidates[:target_count]

        # 重みを小幅調整（rating中心に）
        adjusted_weights = weights.copy()
        adjusted_weights["rating"] = min(0.5, adjusted_weights.get("rating", 0.4) + 0.1)

        print(f"✅ フォールバック再ランキング完了: {len(selected)}個")
        return selected, adjusted_weights
