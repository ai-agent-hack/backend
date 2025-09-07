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

    async def text_search_optimized(
        self,
        query: str,
        region: str,
        max_results: int = 60,
        language: str = "ja",
        type: Optional[str] = None,
    ) -> List[str]:
        """
        🚀 最適化されたテキスト検索: 1ページ目 + ページネーション並列処理

        Args:
            query: 検索クエリ
            region: 検索地域
            max_results: 最大結果数 (60個)
            language: 言語
            type: 場所タイプ

        Returns:
            place_idリスト (最大60個)
        """
        if not self.gmaps:
            print("⚠️ Google Maps API이용不可。フォールバック使用")
            return [f"fallback_place_{hash(query)}_{i}" for i in range(20)]

        try:
            print(f"🚀 最適化されたPlaces Text Search: '{query}' in {region}")

            # 検索クエリ生成
            search_query = f"{query} {region}"
            country_code = await self._detect_country_from_region(region)

            # 最初のページを検索 (非同期に変換)
            loop = asyncio.get_event_loop()
            first_results = await loop.run_in_executor(
                None,
                lambda: self.gmaps.places(
                    query=search_query,
                    language=language,
                    region=country_code,
                    type=type,
                )
            )

            all_place_ids = []

            # 첫 번째 페이지 결과 처리
            if first_results.get("results"):
                for place in first_results["results"]:
                    if place.get("place_id"):
                        all_place_ids.append(place["place_id"])

            print(f"📄 첫 번째 페이지: {len(all_place_ids)}개")

            # next_page_token이 있으면 추가 페이지들을 병렬 처리
            next_page_token = first_results.get("next_page_token")
            if next_page_token and len(all_place_ids) < max_results:
                # 2-3페이지를 병렬로 가져오기
                additional_pages = await self._get_additional_pages_parallel(
                    next_page_token,
                    search_query,
                    language,
                    country_code,
                    type,
                    max_results - len(all_place_ids),
                )
                all_place_ids.extend(additional_pages)

            print(f"✅ 총 {len(all_place_ids)}개의 place_id 취득: {query}")
            return all_place_ids[:max_results]

        except Exception as e:
            print(f"❌ 최적화된 Places Text Search 실패 '{query}': {str(e)}")
            return [f"error_place_{hash(query)}_{i}" for i in range(10)]

    async def _get_additional_pages_parallel(
        self,
        initial_token: str,
        search_query: str,
        language: str,
        country_code: str,
        type: Optional[str],
        remaining_needed: int,
    ) -> List[str]:
        """
        🔥 추가 페이지들을 병렬로 가져오기
        """
        additional_place_ids = []

        try:
            # トークンがアクティブになるまで待機 (Google API要件)
            await asyncio.sleep(2)

            # 2ページ目を取得 (非同期)
            loop = asyncio.get_event_loop()
            second_results = await loop.run_in_executor(
                None,
                lambda: self.gmaps.places(
                    query=search_query,
                    language=language,
                    region=country_code,
                    type=type,
                    page_token=initial_token,
                )
            )

            if second_results.get("results"):
                for place in second_results["results"]:
                    if place.get("place_id"):
                        additional_place_ids.append(place["place_id"])

            print(f"📄 두 번째 페이지: {len(additional_place_ids)}개")

            # 3페이지가 필요하고 토큰이 있으면 계속
            if len(additional_place_ids) < remaining_needed and second_results.get(
                "next_page_token"
            ):

                await asyncio.sleep(2)

                # 3ページ目も非同期で
                third_results = await loop.run_in_executor(
                    None,
                    lambda: self.gmaps.places(
                        query=search_query,
                        language=language,
                        region=country_code,
                        type=type,
                        page_token=second_results["next_page_token"],
                    )
                )

                if third_results.get("results"):
                    for place in third_results["results"]:
                        if (
                            place.get("place_id")
                            and len(additional_place_ids) < remaining_needed
                        ):
                            additional_place_ids.append(place["place_id"])

                print(f"📄 세 번째 페이지: {len(additional_place_ids)}개 (총합)")

        except Exception as e:
            print(f"❌ 추가 페이지 처리 실패: {str(e)}")

        return additional_place_ids

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

            # バッチごとに並列処理
            batch_size = 10
            batches = [place_ids[i:i+batch_size] for i in range(0, len(place_ids), batch_size)]
            
            for batch_idx, batch in enumerate(batches):
                print(f"📦 バッチ {batch_idx+1}/{len(batches)} 処理中...")
                
                # バッチ内で並列処理
                batch_tasks = []
                for place_id in batch:
                    task = self._get_place_detail_async(place_id)
                    batch_tasks.append(task)
                
                # バッチ内の全タスクを並列実行
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # 成功した結果のみ追加
                for result in batch_results:
                    if not isinstance(result, Exception) and result:
                        places_details.append(result)
                
                # バッチ間で少し待機（Rate Limit対策）
                if batch_idx < len(batches) - 1:
                    await asyncio.sleep(0.5)

            print(f"✅ {len(places_details)}個の詳細情報取得完了")
            return places_details

        except Exception as e:
            print(f"❌ Places Details一括取得失敗: {str(e)}")
            return self._create_fallback_places(place_ids)
    
    async def _get_place_detail_async(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        単一のPlace Detailを非同期で取得
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.gmaps.place(
                    place_id=place_id,
                    fields=[
                        "place_id",
                        "name",
                        "formatted_address",
                        "geometry",
                        "rating",
                        "user_ratings_total",
                        "price_level",
                        "types",
                        "photos",
                        "opening_hours",
                        "website",
                        "formatted_phone_number",
                        "reviews",
                    ],
                    language="ja",
                )
            )
            
            if result.get("result"):
                return self._format_place_details(result["result"])
            return None
            
        except Exception as e:
            print(f"❌ Place Details取得失敗 {place_id}: {str(e)}")
            return None

    def _format_place_details(self, place_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Places API結果をフォーマット
        """
        
        geometry = place_data.get("geometry", {})
        location = geometry.get("location", {})

        # photoかphotosかを動的に判断
        photo_field = place_data.get("photos") or place_data.get("photo", [])

        return {
            "place_id": place_data.get("place_id"),
            "name": place_data.get("name"),
            "address": place_data.get("formatted_address"),
            "lat": location.get("lat"),
            "lng": location.get("lng"),
            "rating": place_data.get("rating", 0.0),
            "ratings_total": place_data.get("user_ratings_total", 0),
            "price_level": place_data.get("price_level", 0),
            "types": place_data.get("types", []),  # 正しいフィールド名
            "photos": self._extract_photo_urls(photo_field),  # 動的に選択されたフィールドを使用
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
        
        # photosが実際にリストかチェック
        if not isinstance(photos, list):
            # 単一のphotoオブジェクトの場合の処理
            if isinstance(photos, dict):
                photos = [photos]
            else:
                return []

        photo_urls = []
        for photo in photos[:3]:  # 最大3枚
            if isinstance(photo, dict) and photo.get("photo_reference"):
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

            # Google Geocoding APIで地域情報を照会（非同期）
            loop = asyncio.get_event_loop()
            geocode_result = await loop.run_in_executor(
                None,
                lambda: self.gmaps.geocode(region, language="en")
            )

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
            keyword in region_lower
            for keyword in ["フランス", "france", "パリ", "paris"]
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

    async def get_place_details_ultra_batch(
        self, place_ids: List[str], batch_size: int = 20
    ) -> List[Dict[str, Any]]:
        """
        🚀 울트라 배치 처리: 대량 place_id를 효율적으로 병렬 처리

        Args:
            place_ids: place_id 리스트
            batch_size: 배치 크기 (기본 20개)

        Returns:
            장소 상세정보 리스트
        """
        if not self.gmaps:
            print("⚠️ Google Maps API 이용불가. 폴백 사용")
            return self._create_fallback_places(place_ids)

        try:
            print(
                f"🚀 울트라 배치 Details: {len(place_ids)}개 → {batch_size}개씩 병렬 처리"
            )

            # 배치로 나누기
            batches = [
                place_ids[i : i + batch_size]
                for i in range(0, len(place_ids), batch_size)
            ]

            print(f"📦 총 {len(batches)}개 배치로 분할")

            # 모든 배치를 병렬로 처리
            batch_tasks = [
                self._process_details_batch(batch, batch_idx)
                for batch_idx, batch in enumerate(batches)
            ]

            # 병렬 실행
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # 결과 통합
            all_details = []
            successful_batches = 0

            for result in batch_results:
                if not isinstance(result, Exception) and result:
                    all_details.extend(result)
                    successful_batches += 1
                else:
                    print(f"⚠️ 배치 처리 실패: {result}")

            print(
                f"✅ 울트라 배치 완료: {successful_batches}/{len(batches)} 배치 성공, {len(all_details)}개 Details"
            )
            return all_details

        except Exception as e:
            print(f"❌ 울트라 배치 처리 실패: {str(e)}")
            return self._create_fallback_places(place_ids)

    async def _process_details_batch(
        self, place_ids_batch: List[str], batch_idx: int
    ) -> List[Dict[str, Any]]:
        """
        🔥 個別バッチ処理 (並列内部ロジック)
        """
        batch_details = []

        try:
            print(f"📦 バッチ {batch_idx} 処理開始: {len(place_ids_batch)}個")

            # セマフォアで同時実行を制限 (Rate Limit対応)
            semaphore = asyncio.Semaphore(5)  # 同時5個まで
            
            async def get_with_semaphore(place_id):
                async with semaphore:
                    return await self._get_single_place_detail(place_id)
            
            # 個別Details APIコールを非同期で処理
            detail_tasks = [
                get_with_semaphore(place_id) for place_id in place_ids_batch
            ]

            # 全詳細タスクを即座に並列実行
            completed_details = await asyncio.gather(
                *detail_tasks, return_exceptions=True
            )

            # 成功した結果のみ収集
            for detail in completed_details:
                if not isinstance(detail, Exception) and detail:
                    batch_details.append(detail)

            print(
                f"✅ バッチ {batch_idx} 完了: {len(batch_details)}/{len(place_ids_batch)}個成功"
            )

        except Exception as e:
            print(f"❌ バッチ {batch_idx} 失敗: {str(e)}")

        return batch_details

    async def _get_single_place_detail(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        ⚡ 単一Place Detail照会 (非同期最適化)
        """
        try:
            loop = asyncio.get_event_loop()
            # Places Details APIコール (非同期)
            result = await loop.run_in_executor(
                None,
                lambda: self.gmaps.place(
                    place_id=place_id,
                    fields=[
                        "place_id",
                        "name",
                        "formatted_address",
                        "geometry",
                        "rating",
                        "user_ratings_total",
                        "price_level",
                        "type",
                        "photo",
                        "opening_hours",
                        "website",
                        "formatted_phone_number",
                        "reviews",
                    ],
                    language="ja",
                )
            )

            if result.get("result"):
                return self._format_place_details(result["result"])

        except Exception as e:
            print(f"❌ Single Details 실패 {place_id}: {str(e)}")

        return None
