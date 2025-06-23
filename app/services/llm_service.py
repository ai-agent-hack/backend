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
        Step 3-6: LLM재랭킹 + 가중치 조정 (80개 → 40개)

        Args:
            candidates: 80개 후보 장소 리스트
            weights: 현재 가중치
            pre_info: 사용자 여행정보
            target_count: 선별할 장소 수 (기본 40개)

        Returns:
            tuple: (재랭킹된 40개 장소, 조정된 가중치)
        """
        if not self.model:
            print("⚠️ Vertex AI モデルがありません。フォールバック使用")
            return self._fallback_reranking(candidates, weights, target_count)

        try:
            print(f"🤖 LLM再ランキング開始: {len(candidates)}個 → {target_count}個")

            # 프롬프트 생성
            prompt = self._create_rerank_prompt(
                candidates, weights, pre_info, target_count
            )

            generation_config = GenerationConfig(
                temperature=0.3,  # 일관성 중시
                top_p=0.8,
                max_output_tokens=2048,
                response_mime_type="application/json",
            )

            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
            )

            # JSON 응답 파싱
            result = json.loads(response.text)

            # 선별된 장소 ID 리스트
            selected_place_ids = result.get("selected_place_ids", [])
            adjusted_weights = result.get("adjusted_weights", weights)
            reasoning = result.get("reasoning", "재랭킹 완료")

            # 가중치를 float로 변환
            converted_weights = {}
            for key, value in adjusted_weights.items():
                try:
                    converted_weights[key] = float(value)
                except (ValueError, TypeError):
                    converted_weights[key] = weights.get(key, 0.25)  # 기본값 사용

            # 선별된 장소들을 순서대로 정렬
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

            # 부족한 경우 남은 후보에서 보완
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
        """재랭킹용 프롬프트 생성"""

        # 후보 장소들을 요약 형태로 변환
        candidate_summaries = []
        for i, place in enumerate(candidates[:80]):  # 최대 80개만
            summary = {
                "id": place.get("place_id", f"place_{i}"),
                "name": place.get("name", f"장소_{i}"),
                "rating": place.get("rating", 0.0),
                "price_level": place.get("price_level", 2),
                "address": place.get("address", "주소정보없음")[:50],  # 주소 길이 제한
                "types": place.get("types", [])[:3],  # 타입 개수 제한
                "similarity_score": place.get("similarity_score", 0.5),
            }
            candidate_summaries.append(summary)

        prompt = f"""
다음은 여행 추천 시스템의 장소 재랭킹 작업입니다. 80개 후보 중에서 사용자에게 가장 적합한 {target_count}개를 선별해주세요.

**사용자 여행정보:**
- 지역: {pre_info.region}
- 예산: {pre_info.budget_per_person:,}원
- 인원: {pre_info.participants_count}명
- 분위기 선호: {pre_info.atmosphere}
- 기간: {pre_info.start_date} ~ {pre_info.end_date}

**현재 가중치:**
{json.dumps(weights, indent=2, ensure_ascii=False)}

**후보 장소들 (80개):**
{json.dumps(candidate_summaries, indent=2, ensure_ascii=False)}

**작업 요구사항:**

1. **개인화 필터링**: 사용자의 예산, 분위기, 인원수를 고려하여 부적합한 장소 제외
   - 예산 초과 장소 필터링 (price_level 4 = 고급, 3 = 중급, 2 = 보통, 1 = 저렴)
   - 분위기에 맞지 않는 장소 제외
   - 그룹 규모에 부적합한 장소 제외

2. **다양성 보장**: 카테고리별 균형 유지
   - 음식점, 관광지, 문화시설, 쇼핑 등 다양한 타입 포함
   - 동일 지역 집중 방지

3. **품질 우선순위**: 
   - 평점 4.0 이상 우선 선택
   - 리뷰 수가 많은 신뢰할 만한 장소 우선
   - Vector 유사도 점수 고려

4. **가중치 조정**: 사용자 프로필에 따라 가중치 미세조정
   - 예산 제약 강할 시 → price 가중치 증가
   - 분위기 중시 → similarity, congestion 가중치 증가
   - 안전성 중시 → rating 가중치 증가

**응답 형식 (JSON):**
```json
{{
  "selected_place_ids": ["place_id_1", "place_id_2", ..., "place_id_{target_count}"],
  "adjusted_weights": {{
    "price": 0.35,
    "rating": 0.35,
    "congestion": 0.20,
    "similarity": 0.10
  }},
  "reasoning": "선별 기준과 가중치 조정 이유를 2-3문장으로 설명",
  "category_distribution": {{
    "restaurant": 12,
    "tourist_attraction": 8,
    "shopping": 5,
    "cultural": 6,
    "other": 9
  }}
}}
```

사용자의 '{pre_info.atmosphere}' 분위기와 예산 {pre_info.budget_per_person:,}원을 핵심 기준으로 최적의 {target_count}개를 선별해주세요.
"""
        return prompt

    def _fallback_reranking(
        self,
        candidates: List[Dict[str, Any]],
        weights: Dict[str, float],
        target_count: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        """LLM 재랭킹 실패 시 폴백 로직"""
        print(f"🔄 폴백 재랭킹: {len(candidates)}개 → {target_count}개")

        # 평점 기준으로 정렬
        sorted_candidates = sorted(
            candidates,
            key=lambda x: (
                x.get("rating", 0.0) * 0.6 + x.get("similarity_score", 0.0) * 0.4
            ),
            reverse=True,
        )

        # 상위 target_count개 선택
        selected = sorted_candidates[:target_count]

        # 가중치 소폭 조정 (rating 중심으로)
        adjusted_weights = weights.copy()
        adjusted_weights["rating"] = min(0.5, adjusted_weights.get("rating", 0.4) + 0.1)

        print(f"✅ 폴백 재랭킹 완료: {len(selected)}개")
        return selected, adjusted_weights
