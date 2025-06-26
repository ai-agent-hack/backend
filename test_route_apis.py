#!/usr/bin/env python3
"""
Route API 테스트 스크립트

/api/v1/route/regenerate와 /api/v1/route/{plan_id}/{version}/partial-update
API들을 테스트합니다.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1/route"


def test_regenerate_api():
    """
    POST /regenerate API 테스트
    기존 버전의 스팟들을 새 버전으로 복사하고 다른 설정으로 경로 재계산
    """
    print("=== Testing POST /regenerate ===")

    url = f"{BASE_URL}/regenerate"
    payload = {
        "plan_id": "rec_1750831581",
        "version": 4,  # 기존 버전
        "departure_location": "인천국제공항",
        "hotel_location": "강남역",
        "travel_mode": "DRIVING",
        "optimize_for": "distance",
    }

    print(f"Request: POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()

    return response.json()


def test_partial_update_hotel():
    """
    PATCH /partial-update - hotel_location 변경 테스트
    """
    print("=== Testing PATCH /partial-update - hotel_location ===")

    plan_id = "rec_1750831581"
    version = 4
    url = f"{BASE_URL}/{plan_id}/{version}/partial-update"

    payload = {"type": "hotel_location", "hotel_location": "홍대입구역"}

    print(f"Request: PATCH {url}")
    print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    response = requests.patch(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()


def test_partial_update_travel_mode():
    """
    PATCH /partial-update - travel_mode 변경 테스트
    """
    print("=== Testing PATCH /partial-update - travel_mode ===")

    plan_id = "rec_1750831581"
    version = 4
    url = f"{BASE_URL}/{plan_id}/{version}/partial-update"

    payload = {"type": "travel_mode", "travel_mode": "TRANSIT"}

    print(f"Request: PATCH {url}")
    print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    response = requests.patch(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()


def test_partial_update_day_reorder():
    """
    PATCH /partial-update - day_reorder 테스트
    """
    print("=== Testing PATCH /partial-update - day_reorder ===")

    plan_id = "rec_1750831581"
    version = 4
    url = f"{BASE_URL}/{plan_id}/{version}/partial-update"

    payload = {
        "type": "day_reorder",
        "day_number": 1,
        "spot_order": ["M3", "M1", "M2", "M4", "M5"],
    }

    print(f"Request: PATCH {url}")
    print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    response = requests.patch(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()


def test_partial_update_spot_replacement():
    """
    PATCH /partial-update - spot_replacement 테스트
    """
    print("=== Testing PATCH /partial-update - spot_replacement ===")

    plan_id = "rec_1750831581"
    version = 4
    url = f"{BASE_URL}/{plan_id}/{version}/partial-update"

    payload = {"type": "spot_replacement", "old_spot_id": "M5", "new_spot_id": "M10"}

    print(f"Request: PATCH {url}")
    print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    response = requests.patch(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()


def test_get_route_details():
    """
    GET /{plan_id}/{version} - 경로 상세 정보 조회
    """
    print("=== Testing GET /{plan_id}/{version} ===")

    plan_id = "rec_1750831581"
    version = 4
    url = f"{BASE_URL}/{plan_id}/{version}"

    print(f"Request: GET {url}")

    response = requests.get(url)
    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Route ID: {data.get('route_id')}")
        print(f"Total Distance: {data.get('total_distance_km')} km")
        print(f"Total Duration: {data.get('total_duration_minutes')} min")
        print(f"Total Days: {len(data.get('days', []))}")
    else:
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()


def main():
    """
    모든 테스트 실행
    """
    print("Route API 테스트 시작")
    print("=" * 50)

    try:
        # 1. regenerate API 테스트
        # test_regenerate_api()

        # 2. partial update 테스트들
        test_partial_update_hotel()
        test_partial_update_travel_mode()
        test_partial_update_day_reorder()
        test_partial_update_spot_replacement()

        # 3. 경로 상세 정보 조회
        test_get_route_details()

        print("=" * 50)
        print("모든 테스트 완료!")

    except requests.exceptions.ConnectionError:
        print(
            "❌ 연결 오류: FastAPI 서버가 실행 중인지 확인하세요 (http://localhost:8000)"
        )
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


if __name__ == "__main__":
    main()
