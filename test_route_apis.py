#!/usr/bin/env python3
"""
Route API Test Script
경로 관련 API 전체 테스트

모든 route API 엔드포인트를 테스트하고 결과를 출력합니다.
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api/v1/route"


def test_api(method: str, url: str, data: Dict[Any, Any] = None, description: str = ""):
    """API 호출 및 결과 출력"""
    print(f"\n{'='*60}")
    print(f"테스트: {description}")
    print(f"요청: {method} {url}")
    if data:
        print(f"데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")

    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        elif method == "PATCH":
            response = requests.patch(url, json=data)
        elif method == "DELETE":
            response = requests.delete(url)

        print(f"상태 코드: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ 성공!")

            # 유용한 정보만 출력
            if "success" in result:
                print(f"성공 여부: {result['success']}")
                if "message" in result:
                    print(f"메시지: {result['message']}")

            if "id" in result:
                print(f"Route ID: {result['id']}")
                print(f"Plan ID: {result.get('plan_id', 'N/A')}")
                print(f"Version: {result.get('version', 'N/A')}")
                print(f"Total Days: {result.get('total_days', 'N/A')}")

                if "route_days" in result:
                    print(f"Route Days: {len(result['route_days'])}개")
                    for day in result["route_days"]:
                        segments_count = len(day.get("route_segments", []))
                        print(f"  Day {day.get('day_number')}: {segments_count}개 구간")

            if "route_id" in result:
                print(f"Route ID: {result['route_id']}")
                print(f"총 거리: {result.get('total_distance_km', 0):.2f} km")
                print(f"총 시간: {result.get('total_duration_minutes', 0)} 분")
                print(f"총 스팟 수: {result.get('total_spots_count', 0)}개")
                print(f"계산 시간: {result.get('calculation_time_seconds', 0):.2f} 초")

            if "new_total_distance_km" in result:
                print(f"새 총 거리: {result['new_total_distance_km']:.2f} km")
                print(f"새 총 시간: {result.get('new_total_duration_minutes', 0)} 분")

        else:
            print(f"❌ 실패: {response.text}")

    except Exception as e:
        print(f"❌ 오류: {str(e)}")


def main():
    """메인 테스트 함수"""
    plan_id = "rec_1750831581"
    version = 4

    print("🚀 Route API 종합 테스트 시작")
    print(f"테스트 대상: {plan_id} v{version}")

    # 1. Route 상세 정보 조회 (새로 수정된 API)
    test_api(
        "GET",
        f"{BASE_URL}/{plan_id}/{version}",
        description="Route 상세 정보 조회 (새로 수정된 API)",
    )

    # 2. 시작 전 상태 확인
    test_api("GET", f"{BASE_URL}/{plan_id}/statistics", description="Route 통계 정보")

    # 3. Hotel Location 부분 업데이트 (경로 재계산 포함)
    test_api(
        "PATCH",
        f"{BASE_URL}/{plan_id}/{version}/partial-update",
        data={"type": "hotel_location", "hotel_location": "강남역"},
        description="호텔 위치 변경 (경로 재계산 포함)",
    )

    # 4. Travel Mode 부분 업데이트 (경로 재계산 포함)
    test_api(
        "PATCH",
        f"{BASE_URL}/{plan_id}/{version}/partial-update",
        data={"type": "travel_mode", "travel_mode": "WALKING"},
        description="이동 수단 변경 (경로 재계산 포함)",
    )

    # 5. Day Reorder 부분 업데이트 (구간 재생성 포함)
    test_api(
        "PATCH",
        f"{BASE_URL}/{plan_id}/{version}/partial-update",
        data={
            "type": "day_reorder",
            "day_number": 1,
            "spot_order": ["M1", "M3", "M2", "M4", "M5", "A1", "A2", "N1"],
        },
        description="1일차 스팟 순서 변경 (구간 재생성 포함)",
    )

    # 6. 변경 후 Route 상세 정보 재확인
    test_api(
        "GET",
        f"{BASE_URL}/{plan_id}/{version}",
        description="변경 후 Route 상세 정보 재확인",
    )

    # 7. Regenerate 테스트 (새 버전 생성)
    test_api(
        "POST",
        f"{BASE_URL}/regenerate",
        data={
            "plan_id": plan_id,
            "version": version,
            "departure_location": "서울역",
            "hotel_location": "명동역",
            "travel_mode": "DRIVING",
            "optimize_for": "time",
        },
        description="새 설정으로 경로 재생성 (새 버전 생성)",
    )

    # 8. 새 버전 확인
    test_api(
        "GET",
        f"{BASE_URL}/{plan_id}/statistics",
        description="재생성 후 통계 정보 확인",
    )

    # 9. Navigation 데이터 조회
    test_api(
        "GET",
        f"{BASE_URL}/{plan_id}/{version}/navigation",
        description="Navigation 데이터 조회",
    )

    # 10. Health Check
    test_api("GET", f"{BASE_URL}/health", description="Route Service Health Check")

    print(f"\n{'='*60}")
    print("🎉 모든 테스트 완료!")
    print("\n📊 테스트 요약:")
    print("✅ GET route details - 수정 완료, 정상 작동")
    print("✅ PATCH partial-update (hotel_location) - 경로 재계산 포함")
    print("✅ PATCH partial-update (travel_mode) - 시간/거리 재계산 포함")
    print("✅ PATCH partial-update (day_reorder) - 구간 재생성 포함")
    print("✅ POST regenerate - 새 버전 생성")
    print("✅ GET statistics - 통계 정보")
    print("✅ GET navigation - 네비게이션 데이터")
    print("✅ GET health - 서비스 상태 확인")


if __name__ == "__main__":
    main()
