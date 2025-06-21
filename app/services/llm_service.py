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
- 出発地: {pre_info.departure_location}
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
            "서울": ["ソウル カフェ", "江南 グルメ", "漢江 公園"],
            "부산": ["釜山 海岸", "広安里", "甘川文化村"],
            "제주": ["済州 自然", "漢拏山", "済州 カフェ"],
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
        Step 3-6: LLMを使用した再ランキングと重み調整 (80個 → 40個)

        Args:
            candidates: 80個候補スポットリスト
            weights: 現在の重み
            pre_info: ユーザー旅行情報
            target_count: 目標個数 (デフォルト40個)

        Returns:
            tuple: (再ランキングされたスポットリスト, 調整された重み)
        """
        if not self.model or len(candidates) <= target_count:
            print("⚠️ LLM再ランキング フォールバック使用")
            # フォールバック: 単純上位選択 + 重み調整
            reranked = candidates[:target_count]

            # 安全な重み調整 (タイプ確認)
            rating_value = weights.get("rating", 0.4)
            try:
                rating_float = float(rating_value)
            except (ValueError, TypeError):
                rating_float = 0.4

            adjusted_weights = {**weights}
            adjusted_weights["rating"] = min(
                rating_float + 0.1, 1.0
            )  # 1.0を超えないように

            return reranked, adjusted_weights

        try:
            # 候補スポット要約 (長すぎるとトークン制限に引っかかる)
            candidates_summary = [
                {
                    "place_id": spot.get("place_id", "unknown"),
                    "name": spot.get("name", "unknown"),
                    "rating": spot.get("rating", 0),
                }
                for spot in candidates[:20]  # 最初の20個だけLLMに送信
            ]

            prompt = self._create_rerank_prompt(
                candidates_summary, weights, pre_info, target_count
            )

            generation_config = GenerationConfig(
                temperature=0.5,
                top_p=0.9,
                max_output_tokens=2048,
                response_mime_type="application/json",
            )

            print(
                f"🔄 LLM再ランキング要請中... ({len(candidates)}個 → {target_count}個)"
            )
            response = self.model.generate_content(
                prompt, generation_config=generation_config
            )
            result = json.loads(response.text)

            # 結果処理
            selected_place_ids = result.get("selected_place_ids", [])
            adjusted_weights = result.get("adjusted_weights", weights)

            # 重み値をfloatに変換
            converted_adjusted_weights = {}
            for key, value in adjusted_weights.items():
                try:
                    converted_adjusted_weights[key] = float(value)
                except (ValueError, TypeError):
                    converted_adjusted_weights[key] = weights.get(
                        key, 0.1
                    )  # 元の値またはデフォルト値

            # place_idベースで再ランキング
            reranked = []
            for place_id in selected_place_ids:
                for candidate in candidates:
                    if candidate.get("place_id") == place_id:
                        reranked.append(candidate)
                        break

            # 不足分を元から補充
            while len(reranked) < target_count and len(reranked) < len(candidates):
                for candidate in candidates:
                    if candidate not in reranked:
                        reranked.append(candidate)
                        if len(reranked) >= target_count:
                            break

            print(f"✅ LLM再ランキング完了: {len(reranked)}個選別")
            return reranked[:target_count], converted_adjusted_weights

        except Exception as e:
            print(f"❌ LLM再ランキング失敗: {str(e)}")
            # フォールバック
            reranked = candidates[:target_count]

            rating_value = weights.get("rating", 0.4)
            try:
                rating_float = float(rating_value)
            except (ValueError, TypeError):
                rating_float = 0.4

            adjusted_weights = {**weights}
            adjusted_weights["rating"] = min(rating_float + 0.1, 1.0)

            return reranked, adjusted_weights

    def _create_rerank_prompt(
        self,
        candidates: List[Dict[str, Any]],
        weights: Dict[str, float],
        pre_info: PreInfo,
        target_count: int,
    ) -> str:
        """再ランキング用プロンプト生成"""
        candidates_text = "\n".join(
            [
                f"- {c['place_id']}: {c['name']} (評点: {c['rating']})"
                for c in candidates
            ]
        )

        prompt = f"""
以下のスポット候補をユーザーの旅行嗜好に合わせて再ランキングし、重みを調整してください。

**ユーザー旅行情報:**
- 地域: {pre_info.region}
- 予算: {pre_info.budget:,}円
- 雰囲気: {pre_info.atmosphere}

**現在の重み:**
{json.dumps(weights, ensure_ascii=False, indent=2)}

**スポット候補:**
{candidates_text}

**要求事項:**
1. 上位{target_count}個のスポットを選別してplace_id順序で配列
2. ユーザーの雰囲気嗜好に合わせて重みを微調整 (合計1.0維持)

**応答形式 (JSON):**
{{
  "selected_place_ids": ["place_id_1", "place_id_2", ...],
  "adjusted_weights": {{
    "price": 0.3,
    "rating": 0.4,
    "congestion": 0.2,
    "similarity": 0.1
  }},
  "reasoning": "選別と重み調整の理由"
}}
"""
        return prompt
