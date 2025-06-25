# 🗄️ DB 스키마 개선 계획

## 📋 현재 문제점

### 현재 rec_spot 테이블 구조:

```sql
- id (PK)
- plan_id
- version
- spot_id           -- Google Places ID만
- rank              -- 순서만
- status            -- ADD/KEEP/DEL만
- similarity_score  -- 유사도만
- created_at, updated_at
```

### 누락된 중요 데이터:

-   ❌ **위도/경도**: Route 계산 필수
-   ❌ **시간대**: 오전/오후/저녁 분배 정보
-   ❌ **스팟 상세정보**: 이름, 혼잡도, 영업시간 등
-   ❌ **추천 이유**: 사용자에게 보여줄 이유
-   ❌ **이미지/웹사이트**: 프론트엔드 표시용

## 🎯 개선 방향

### Option 1: rec_spot 테이블 확장 (권장)

```sql
ALTER TABLE rec_spot ADD COLUMN:
- time_slot VARCHAR(10)          -- '午前', '午後', '夜'
- latitude DECIMAL(10,8)         -- 위도
- longitude DECIMAL(11,8)        -- 경도
- spot_name VARCHAR(200)         -- 스팟 이름
- spot_details JSONB             -- 혼잡도, 영업시간 등
- recommendation_reason TEXT     -- 추천 이유
- image_url TEXT                 -- 이미지 URL
- website_url TEXT               -- 웹사이트 URL
- selected BOOLEAN DEFAULT false -- 사용자 선택 여부
```

### Option 2: 별도 테이블 분리

```sql
-- 기본 정보 테이블 (무거운 데이터)
CREATE TABLE spot_details (
    spot_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200),
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    details JSONB,
    image_url TEXT,
    website_url TEXT,
    updated_at TIMESTAMP
);

-- rec_spot은 관계 정보만
rec_spot + time_slot, recommendation_reason, selected
```

## 🚀 구현 단계

### 1단계: Migration 생성

-   [ ] Alembic migration 파일 생성
-   [ ] 테이블 구조 변경
-   [ ] 기존 데이터 호환성 확인

### 2단계: 저장 로직 수정

-   [ ] save_spots_for_plan_version() 수정
-   [ ] RecommendSpots → DB 저장 시 모든 데이터 포함
-   [ ] 시간대별 분배 정보 저장

### 3단계: 조회 로직 수정

-   [ ] convert_rec_spots_to_recommend_spots() 수정
-   [ ] 저장된 데이터 기반 응답
-   [ ] 더미 데이터 제거

### 4단계: API 응답 개선

-   [ ] GET /trip/{plan_id} 실제 데이터 반환
-   [ ] 시간대별 분배 정확히 표시
-   [ ] Route 계산용 위도/경도 준비

## 💾 저장 시점 전략

### refine 과정:

-   메모리에서만 처리 (현재와 동일)
-   사용자가 여러 번 수정 가능

### save 시점:

-   **모든 상세 정보를 DB에 완전 저장**
-   시간대별 분배, 위도/경도, 혼잡도 등
-   이후 조회 시 빠른 응답 + Route 계산 준비

## 🎯 최종 목표

```json
// save 후 GET /trip/{plan_id} 응답
{
  "recommend_spots": [
    {
      "time_slot": "午前",
      "spots": [
        {
          "spot_id": "ChIJxxxxx",
          "latitude": 37.5513,     // 실제 저장된 위도
          "longitude": 126.9882,   // 실제 저장된 경도
          "details": {
            "name": "남산타워",     // 실제 저장된 이름
            "congestion": [25,30,35...], // 실제 저장된 혼잡도
            "business_hours": {...}
          },
          "recommendation_reason": "오전 혼잡도가 낮아 추천드립니다"
        }
      ]
    }
  ]
}
```

**Route 계산 시 사용할 수 있는 완전한 데이터 확보!** 🎉
