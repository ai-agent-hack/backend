import time
from typing import List, Dict, Any
from pytrends.request import TrendReq
import pandas as pd


class GoogleTrendsService:
    """
    Google Trendsサービス
    pytrendsライブラリを使用してキーワードの人気度をチェック
    """

    def __init__(self):
        try:
            print("🔥 GoogleTrendsService初期化開始...")
            # Google Trends API 初期化
            self.pytrends = TrendReq(hl="ja-JP", tz=540)  # 日本語、JST
            print("✅ GoogleTrendsService初期化完了")
        except Exception as e:
            print(f"❌ GoogleTrendsService初期化失敗: {str(e)}")
            self.pytrends = None

    async def filter_trending_keywords(
        self, keywords: List[str], threshold: int = 50
    ) -> List[str]:
        """
        キーワードリストから人気のあるものをフィルタリング

        Args:
            keywords: チェックするキーワードリスト
            threshold: 人気度閾値 (0-100、デフォルト50)

        Returns:
            フィルタリングされたキーワードリスト
        """
        if not self.pytrends or not keywords:
            print("⚠️ GoogleTrends利用不可。全キーワード返却")
            return keywords

        try:
            print(f"🔍 Google Trendsキーワード人気度チェック: {keywords}")

            trending_keywords = []

            # 各キーワードの人気度をチェック
            for keyword in keywords:
                try:
                    # API制限を避けるため少し待機
                    time.sleep(1)

                    # 過去30日間のトレンド取得
                    self.pytrends.build_payload(
                        [keyword], timeframe="today 1-m", geo=""
                    )

                    # 時系列データ取得
                    interest_over_time = self.pytrends.interest_over_time()

                    if (
                        not interest_over_time.empty
                        and keyword in interest_over_time.columns
                    ):
                        # 平均人気度計算
                        avg_interest = interest_over_time[keyword].mean()
                        print(f"  📊 {keyword}: 人気度 {avg_interest:.1f}")

                        # 閾値以上なら追加
                        if avg_interest >= threshold:
                            trending_keywords.append(keyword)
                            print(
                                f"  ✅ {keyword}: トレンディング確認 ({avg_interest:.1f} >= {threshold})"
                            )
                        else:
                            print(
                                f"  ❌ {keyword}: 人気度不足 ({avg_interest:.1f} < {threshold})"
                            )
                    else:
                        print(f"  ⚠️ {keyword}: データなし、安全のため含める")
                        trending_keywords.append(keyword)  # データがない場合は含める

                except Exception as e:
                    print(f"  ❌ {keyword}のトレンドチェック失敗: {str(e)}")
                    trending_keywords.append(keyword)  # エラー時は含める

            if not trending_keywords:
                print("⚠️ トレンディングキーワードなし。元のリスト返却")
                return keywords

            print(
                f"🎯 フィルタリング結果: {len(trending_keywords)}/{len(keywords)}個キーワード選択"
            )
            print(f"🔥 選択されたキーワード: {trending_keywords}")

            return trending_keywords

        except Exception as e:
            print(f"❌ Google Trendsフィルタリング失敗: {str(e)}")
            print("🔄 フォールバック: 全キーワード返却")
            return keywords

    async def get_related_keywords(self, keyword: str, limit: int = 5) -> List[str]:
        """
        関連キーワード取得

        Args:
            keyword: 基準キーワード
            limit: 取得する関連キーワード数

        Returns:
            関連キーワードリスト
        """
        if not self.pytrends:
            return []

        try:
            print(f"🔍 関連キーワード検索: {keyword}")

            self.pytrends.build_payload([keyword], timeframe="today 3-m")

            # 関連クエリ取得
            related_queries = self.pytrends.related_queries()

            if keyword in related_queries and "top" in related_queries[keyword]:
                top_queries = related_queries[keyword]["top"]
                if not top_queries.empty:
                    related_keywords = top_queries["query"].head(limit).tolist()
                    print(f"✅ 関連キーワード取得: {related_keywords}")
                    return related_keywords

            print(f"⚠️ {keyword}の関連キーワードなし")
            return []

        except Exception as e:
            print(f"❌ 関連キーワード取得失敗: {str(e)}")
            return []

    async def get_trending_searches(
        self, country: str = "japan", limit: int = 10
    ) -> List[str]:
        """
        現在のトレンディング検索取得

        Args:
            country: 国名 (japan, united_states, etc.)
            limit: 取得する検索語数

        Returns:
            トレンディング検索リスト
        """
        if not self.pytrends:
            return []

        try:
            print(f"🚀 トレンディング検索取得: {country}")

            trending_searches = self.pytrends.trending_searches(pn=country)

            if not trending_searches.empty:
                trending_list = trending_searches[0].head(limit).tolist()
                print(f"🔥 トレンディング検索: {trending_list}")
                return trending_list

            print(f"⚠️ {country}のトレンディング検索データなし")
            return []

        except Exception as e:
            print(f"❌ トレンディング検索取得失敗: {str(e)}")
            return []

    async def check_keyword_popularity(
        self, keyword: str, timeframe: str = "today 1-m"
    ) -> Dict[str, Any]:
        """
        単一キーワードの詳細人気度チェック

        Args:
            keyword: チェックするキーワード
            timeframe: 時間範囲

        Returns:
            人気度情報辞書
        """
        if not self.pytrends:
            return {"keyword": keyword, "popularity": 0, "trend": "unknown"}

        try:
            self.pytrends.build_payload([keyword], timeframe=timeframe)

            # 時系列データ
            interest_data = self.pytrends.interest_over_time()

            # 地域別データ
            regional_data = self.pytrends.interest_by_region()

            result = {
                "keyword": keyword,
                "popularity": 0,
                "trend": "stable",
                "top_regions": [],
                "timeframe": timeframe,
            }

            if not interest_data.empty and keyword in interest_data.columns:
                avg_popularity = interest_data[keyword].mean()
                result["popularity"] = round(avg_popularity, 1)

                # トレンド方向判定
                recent_values = interest_data[keyword].tail(5).values
                if len(recent_values) >= 2:
                    if recent_values[-1] > recent_values[0]:
                        result["trend"] = "rising"
                    elif recent_values[-1] < recent_values[0]:
                        result["trend"] = "falling"

            if not regional_data.empty:
                top_regions = regional_data.nlargest(3, keyword).index.tolist()
                result["top_regions"] = top_regions

            print(f"📊 {keyword}の人気度分析: {result}")
            return result

        except Exception as e:
            print(f"❌ {keyword}の人気度チェック失敗: {str(e)}")
            return {"keyword": keyword, "popularity": 0, "trend": "unknown"}
