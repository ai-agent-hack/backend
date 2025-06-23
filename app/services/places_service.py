import asyncio
import os
from typing import List, Dict, Any, Optional
import googlemaps
from app.models.pre_info import PreInfo


class PlacesService:
    """
    Google Places APIサービス
    """

    def __init__(self):
        try:
            print("🗺️ PlacesService初期化開始...")

            # Google Maps API キー取得
            api_key = os.getenv("GOOGLE_MAP_API_KEY")  # Sを削除
            if not api_key:
                print("⚠️ GOOGLE_MAP_API_KEY環境変数が設定されていません")
                self.gmaps = None
            else:
                self.gmaps = googlemaps.Client(key=api_key)
                print("✅ PlacesService初期化完了")

        except Exception as e:
            print(f"❌ PlacesService初期化失敗: {str(e)}")
            self.gmaps = None

    async def text_search(
        self,
        query: str,
        region: str,
        language: str = "ja",
        radius: int = 10000,
        type: Optional[str] = None,
    ) -> List[str]:
        """
        テキスト検索でplace_idリストを取得

        Args:
            query: 検索クエリ
            region: 検索地域
            language: 言語 (デフォルト: 日本語)
            radius: 検索半径(メートル)
            type: 場所タイプ (restaurant, tourist_attraction, etc.)

        Returns:
            place_idのリスト
        """
        if not self.gmaps:
            print("⚠️ Google Maps API利用不可。フォールバック使用")
            return [f"fallback_place_{hash(query)}_{i}" for i in range(5)]

        try:
            print(f"🔍 Places Text Search: '{query}' in {region}")

            # 検索クエリ作成 (地域を含む)
            search_query = f"{query} {region}"

            # 🎯 スマートなアプローチ: Google Geocoding APIで地域自動認識
            country_code = await self._detect_country_from_region(region)

            print(f"🌍 自動検出された国コード: {country_code} (地域: {region})")

            # Places API検索実行（地域情報を検索語に含む）
            results = self.gmaps.places(
                query=search_query,
                language=language,
                region=country_code,  # 自動検出された国コード使用
                type=type,
            )

            place_ids = []
            if results.get("results"):
                for place in results["results"]:
                    if place.get("place_id"):
                        place_ids.append(place["place_id"])

                print(f"✅ {len(place_ids)}個のplace_id取得: {query}")
            else:
                print(f"⚠️ 検索結果なし: {query}")

            return place_ids[:20]  # 最大20個まで

        except Exception as e:
            print(f"❌ Places Text Search失敗 '{query}': {str(e)}")
            # フォールバック
            return [f"error_place_{hash(query)}_{i}" for i in range(3)]

    async def get_place_details_batch(
        self, place_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        複数のplace_idから詳細情報を一括取得

        Args:
            place_ids: place_idのリスト

        Returns:
            場所詳細情報のリスト
        """
        if not self.gmaps:
            print("⚠️ Google Maps API利用不可。フォールバック使用")
            return self._create_fallback_places(place_ids)

        try:
            print(f"📍 Places Details一括取得: {len(place_ids)}個")

            places_details = []

            for place_id in place_ids:
                try:
                    # API呼び出し間隔調整 (Rate Limit対策)
                    await asyncio.sleep(0.1)

                    # Places Details API呼び出し
                    result = self.gmaps.place(
                        place_id=place_id,
                        fields=[
                            "place_id",
                            "name",
                            "formatted_address",
                            "geometry",
                            "rating",
                            "user_ratings_total",
                            "price_level",
                            "type",  # types → type
                            "photo",  # photos → photo
                            "opening_hours",
                            "website",
                            "formatted_phone_number",
                            "reviews",
                        ],
                        language="ja",
                    )

                    if result.get("result"):
                        place_data = self._format_place_details(result["result"])
                        places_details.append(place_data)

                except Exception as e:
                    print(f"❌ Place Details取得失敗 {place_id}: {str(e)}")
                    # 個別エラーは無視して続行
                    continue

            print(f"✅ {len(places_details)}個の詳細情報取得完了")
            return places_details

        except Exception as e:
            print(f"❌ Places Details一括取得失敗: {str(e)}")
            return self._create_fallback_places(place_ids)

    def _format_place_details(self, place_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Places API結果をフォーマット
        """
        geometry = place_data.get("geometry", {})
        location = geometry.get("location", {})

        return {
            "place_id": place_data.get("place_id"),
            "name": place_data.get("name"),
            "address": place_data.get("formatted_address"),
            "lat": location.get("lat"),
            "lng": location.get("lng"),
            "rating": place_data.get("rating", 0.0),
            "ratings_total": place_data.get("user_ratings_total", 0),
            "price_level": place_data.get("price_level", 0),
            "types": place_data.get("type", []),  # typeに変更
            "photos": self._extract_photo_urls(
                place_data.get("photo", [])
            ),  # photoに変更
            "opening_hours": self._format_opening_hours(
                place_data.get("opening_hours")
            ),
            "website": place_data.get("website"),
            "phone": place_data.get("formatted_phone_number"),
            "reviews": self._format_reviews(place_data.get("reviews", [])),
        }

    def _extract_photo_urls(self, photos: List[Dict]) -> List[str]:
        """
        写真URLを抽出 (最大3枚まで)
        """
        if not self.gmaps or not photos:
            return []

        photo_urls = []
        for photo in photos[:3]:  # 最大3枚
            if photo.get("photo_reference"):
                # Photo APIを使用してURL生成
                url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo['photo_reference']}&key={self.gmaps.key}"
                photo_urls.append(url)

        return photo_urls

    def _format_opening_hours(self, opening_hours: Optional[Dict]) -> Optional[Dict]:
        """
        営業時間情報をフォーマット
        """
        if not opening_hours:
            return None

        return {
            "open_now": opening_hours.get("open_now", False),
            "weekday_text": opening_hours.get("weekday_text", []),
        }

    def _format_reviews(self, reviews: List[Dict]) -> List[Dict]:
        """
        レビュー情報をフォーマット (最大3件まで)
        """
        formatted_reviews = []
        for review in reviews[:3]:  # 最大3件
            formatted_reviews.append(
                {
                    "author_name": review.get("author_name"),
                    "rating": review.get("rating"),
                    "text": review.get("text", "")[:200],  # 最大200文字
                    "time": review.get("time"),
                }
            )
        return formatted_reviews

    def _create_fallback_places(self, place_ids: List[str]) -> List[Dict[str, Any]]:
        """
        フォールバック用のダミー場所データ生成
        """
        fallback_places = []
        for i, place_id in enumerate(place_ids[:10]):  # 最大10個
            fallback_places.append(
                {
                    "place_id": place_id,
                    "name": f"場所_{i+1}",
                    "address": "住所情報なし",
                    "lat": 35.6762 + (i * 0.01),  # 東京付近
                    "lng": 139.6503 + (i * 0.01),
                    "rating": 4.0 + (i % 3) * 0.3,
                    "ratings_total": 100 + i * 10,
                    "price_level": (i % 4) + 1,
                    "types": ["establishment"],
                    "photos": [],
                    "opening_hours": None,
                    "website": None,
                    "phone": None,
                    "reviews": [],
                }
            )
        return fallback_places

    async def nearby_search(
        self,
        location: tuple,  # (lat, lng)
        radius: int = 5000,
        type: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> List[str]:
        """
        位置ベース近隣検索

        Args:
            location: (緯度, 経度)
            radius: 検索半径(メートル)
            type: 場所タイプ
            keyword: キーワード

        Returns:
            place_idのリスト
        """
        if not self.gmaps:
            print("⚠️ Google Maps API利用不可")
            return []

        try:
            print(f"📍 近隣検索: {location}, 半径{radius}m")

            results = self.gmaps.places_nearby(
                location=location,
                radius=radius,
                type=type,
                keyword=keyword,
                language="ja",
            )

            place_ids = []
            if results.get("results"):
                for place in results["results"]:
                    if place.get("place_id"):
                        place_ids.append(place["place_id"])

            print(f"✅ 近隣検索で{len(place_ids)}個発見")
            return place_ids

        except Exception as e:
            print(f"❌ 近隣検索失敗: {str(e)}")
            return []

    async def _detect_country_from_region(self, region: str) -> str:
        """
        🎯 スマートな地域検出: Google Geocoding APIを使用して自動的に国コードを抽出

        Args:
            region: ユーザーが入力した地域名（例: "バルセロナ", "東京品川区", "ソウル"）

        Returns:
            ISO国コード（例: "ES", "JP", "KR"）
        """
        if not self.gmaps:
            print("⚠️ Geocoding API使用不可。デフォルト値を使用")
            return "KR"  # デフォルト値

        try:
            print(f"🔍 Geocoding APIで地域分析中: {region}")

            # Google Geocoding APIで地域情報を照会
            geocode_result = self.gmaps.geocode(region, language="en")

            if geocode_result and len(geocode_result) > 0:
                result = geocode_result[0]

                # address_componentsからcountry情報を抽出
                for component in result.get("address_components", []):
                    if "country" in component.get("types", []):
                        country_code = component.get("short_name", "KR")
                        print(f"✅ 自動検出成功: {region} → {country_code}")
                        return country_code

            # 検出失敗時のフォールバックロジック
            print(f"⚠️ Geocoding結果なし。フォールバックロジック使用: {region}")
            return self._fallback_country_detection(region)

        except Exception as e:
            print(f"❌ Geocoding APIエラー: {str(e)}。フォールバックロジック使用")
            return self._fallback_country_detection(region)

    def _fallback_country_detection(self, region: str) -> str:
        """
        シンプルなフォールバックロジック: 最小限の主要地域マッピング
        """
        region_lower = region.lower()

        # 主要国・地域のみシンプルマッピング
        if any(
            keyword in region_lower
            for keyword in [
                "スペイン",
                "spain",
                "バルセロナ",
                "barcelona",
                "マドリード",
                "madrid",
            ]
        ):
            return "ES"
        elif any(
            keyword in region_lower
            for keyword in ["日本", "japan", "東京", "tokyo", "大阪", "osaka"]
        ):
            return "JP"
        elif any(
            keyword in region_lower
            for keyword in ["韓国", "korea", "ソウル", "seoul", "釜山", "busan"]
        ):
            return "KR"
        elif any(
            keyword in region_lower for keyword in ["フランス", "france", "パリ", "paris"]
        ):
            return "FR"
        elif any(
            keyword in region_lower
            for keyword in ["アメリカ", "usa", "america", "ニューヨーク", "new york"]
        ):
            return "US"
        else:
            print(f"🤔 不明な地域: {region}。デフォルト値(KR)を使用")
            return "KR"  # デフォルト値
