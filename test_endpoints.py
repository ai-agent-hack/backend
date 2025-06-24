import asyncio
import httpx
import json
from datetime import datetime, date
from typing import Dict, Any

# Base URL for API
BASE_URL = "http://localhost:8000/api/v1"

# Test data
TEST_PLAN_ID = "test_plan_12345"

# Sample spot data for testing
SAMPLE_SPOTS = {
    "recommend_spot_id": "test_spots_12345",
    "recommend_spots": [
        {
            "time_slot": "午前",
            "spots": [
                {
                    "spot_id": "spot_001",
                    "longitude": 139.7414,
                    "latitude": 35.6673,
                    "recommendation_reason": "東京駅周辺の人気スポット",
                    "details": {
                        "name": "東京駅",
                        "congestion": [1, 2, 3, 4, 5] + [0] * 19,
                        "business_hours": {
                            day: {"open_time": "09:00:00", "close_time": "18:00:00"}
                            for day in [
                                "MONDAY",
                                "TUESDAY",
                                "WEDNESDAY",
                                "THURSDAY",
                                "FRIDAY",
                                "SATURDAY",
                                "SUNDAY",
                            ]
                        },
                        "price": 0,
                    },
                    "selected": False,
                }
            ],
        },
        {
            "time_slot": "午後",
            "spots": [
                {
                    "spot_id": "spot_002",
                    "longitude": 139.7026,
                    "latitude": 35.6584,
                    "recommendation_reason": "新宿の繁華街",
                    "details": {
                        "name": "新宿駅",
                        "congestion": [2, 3, 4, 5, 6] + [0] * 19,
                        "business_hours": {
                            day: {"open_time": "09:00:00", "close_time": "21:00:00"}
                            for day in [
                                "MONDAY",
                                "TUESDAY",
                                "WEDNESDAY",
                                "THURSDAY",
                                "FRIDAY",
                                "SATURDAY",
                                "SUNDAY",
                            ]
                        },
                        "price": 500,
                    },
                    "selected": True,
                }
            ],
        },
    ],
}

# Sample chat history for refine
SAMPLE_CHAT_HISTORY = [
    {
        "role": "user",
        "message": "もう少し静かな場所がいいです。カフェとか美術館とかどうですか？",
    },
    {
        "role": "assistant",
        "message": "承知いたしました。静かで落ち着いた場所をご提案させていただきますね。",
    },
    {
        "role": "user",
        "message": "予算は3000円くらいまでで、午前中に行けるところがいいです。",
    },
]


class TripEndpointTester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def test_refine_endpoint(self) -> Dict[str, Any]:
        """Test the refine endpoint"""
        print("\n🔄 Testing POST /trip/{plan_id}/refine...")

        refine_data = {
            "recommend_spots": SAMPLE_SPOTS,
            "chat_history": SAMPLE_CHAT_HISTORY,
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/trip/{TEST_PLAN_ID}/refine", json=refine_data
            )

            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print("✅ Refine endpoint working!")
                print(f"  - Recommend spot ID: {result.get('recommend_spot_id')}")
                print(f"  - Spots count: {len(result.get('recommend_spots', []))}")
                return result
            else:
                print(f"❌ Error: {response.text}")
                return None

        except Exception as e:
            print(f"❌ Exception: {e}")
            return None

    async def test_save_endpoint(
        self, refined_spots: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Test the save endpoint"""
        print("\n💾 Testing POST /trip/{plan_id}/save...")

        # Use refined spots if available, otherwise use sample spots
        spots_to_save = refined_spots if refined_spots else SAMPLE_SPOTS

        save_data = {"recommend_spots": spots_to_save}

        try:
            response = await self.client.post(
                f"{self.base_url}/trip/{TEST_PLAN_ID}/save", json=save_data
            )

            print(f"Status: {response.status_code}")
            if response.status_code == 201:
                result = response.json()
                print("✅ Save endpoint working!")
                print(f"  - Plan ID: {result.get('plan_id')}")
                print(
                    f"  - Version: {result.get('old_version')} → {result.get('new_version')}"
                )
                print(f"  - Spots saved: {result.get('spots_saved')}")
                print(f"  - Saved at: {result.get('saved_at')}")
                return result
            else:
                print(f"❌ Error: {response.text}")
                return None

        except Exception as e:
            print(f"❌ Exception: {e}")
            return None

    async def test_get_endpoint(self, version: int = None) -> Dict[str, Any]:
        """Test the get endpoint"""
        version_info = f" (version {version})" if version else " (latest)"
        print(f"\n📖 Testing GET /trip/{TEST_PLAN_ID}{version_info}...")

        params = {"version": version} if version else {}

        try:
            response = await self.client.get(
                f"{self.base_url}/trip/{TEST_PLAN_ID}", params=params
            )

            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                plan_info = result.get("plan_info", {})
                recommend_spots = result.get("recommend_spots", {})

                print("✅ Get endpoint working!")
                print(f"  - Plan ID: {plan_info.get('plan_id')}")
                print(f"  - Version: {plan_info.get('version')}")
                print(f"  - Pre-info ID: {plan_info.get('pre_info_id')}")
                print(f"  - Total spots: {plan_info.get('total_spots')}")
                print(f"  - All versions: {result.get('all_versions')}")
                print(
                    f"  - Recommend spots: {len(recommend_spots.get('recommend_spots', []))}"
                )
                return result
            else:
                print(f"❌ Error: {response.text}")
                return None

        except Exception as e:
            print(f"❌ Exception: {e}")
            return None

    async def run_full_test_suite(self):
        """Run comprehensive test suite for all endpoints"""
        print("🚀 Starting Trip Endpoints Test Suite")
        print("=" * 50)

        # Test 1: Refine endpoint
        refined_result = await self.test_refine_endpoint()

        # Test 2: Save endpoint (using refined result if available)
        save_result = await self.test_save_endpoint(refined_result)

        # Test 3: Get endpoint (latest version)
        get_result = await self.test_get_endpoint()

        # Test 4: Get endpoint (specific version if we saved something)
        if save_result and save_result.get("new_version"):
            await self.test_get_endpoint(save_result["new_version"])

        print("\n" + "=" * 50)
        print("🏁 Test Suite Complete!")


async def main():
    """Main test function"""
    async with TripEndpointTester(BASE_URL) as tester:
        await tester.run_full_test_suite()


if __name__ == "__main__":
    print("🧪 Trip Endpoints Tester")
    print("Make sure the backend server is running on http://localhost:8000")
    print("Testing Plan ID:", TEST_PLAN_ID)

    asyncio.run(main())
