-- Multi-day Route System Database Schema

-- 1. routes 테이블 (메인 경로 정보)
CREATE TABLE routes (
    id SERIAL PRIMARY KEY,
    plan_id VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL,
    
    -- 여행 기본 정보
    total_days INTEGER NOT NULL,              -- 총 여행 일수
    departure_location VARCHAR(200),          -- 출발지
    hotel_location VARCHAR(200),              -- 숙소 위치 (다일차용)
    
    -- 전체 경로 요약
    total_distance_km DECIMAL(8,2),           -- 총 이동거리(km)
    total_duration_minutes INTEGER,           -- 총 소요시간(분)
    total_spots_count INTEGER,                -- 총 스팟 수
    
    -- 메타데이터
    calculated_at TIMESTAMP DEFAULT NOW(),
    google_maps_data JSONB,                   -- Google Maps API 원본 응답 저장
    
    FOREIGN KEY (plan_id, version) REFERENCES rec_plan(plan_id, version),
    UNIQUE(plan_id, version)  -- 플랜 버전당 하나의 경로만
);

-- 2. route_days 테이블 (일차별 경로)
CREATE TABLE route_days (
    id SERIAL PRIMARY KEY,
    route_id INTEGER NOT NULL,
    day_number INTEGER NOT NULL,              -- 1일차, 2일차, 3일차...
    
    -- 일차별 경로 정보
    start_location VARCHAR(200),              -- 일차 시작 위치
    end_location VARCHAR(200),                -- 일차 종료 위치
    day_distance_km DECIMAL(8,2),             -- 일차 총 거리
    day_duration_minutes INTEGER,             -- 일차 총 소요시간
    
    -- 일차별 경로 순서 (TSP 결과)
    ordered_spots JSONB NOT NULL,             -- [{"spot_id": "...", "order": 1, "time_slot": "MORNING", "arrival_time": "09:30"}]
    route_geometry JSONB,                     -- Google Maps Directions 지오메트리
    
    FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE,
    UNIQUE(route_id, day_number)
);

-- 3. route_segments 테이블 (구간별 상세 정보)
CREATE TABLE route_segments (
    id SERIAL PRIMARY KEY,
    route_day_id INTEGER NOT NULL,
    segment_order INTEGER NOT NULL,           -- 구간 순서
    
    -- 구간 정보
    from_location VARCHAR(200),               -- 출발지 (이전 스팟 또는 시작점)
    to_spot_id VARCHAR(100),                  -- 도착 스팟 ID
    to_spot_name VARCHAR(200),                -- 도착 스팟 이름
    
    -- 이동 정보
    distance_meters INTEGER,                  -- 구간 거리(미터)
    duration_seconds INTEGER,                 -- 구간 소요시간(초)
    travel_mode VARCHAR(20) DEFAULT 'DRIVING', -- 이동 수단
    
    -- 상세 경로 안내
    directions_steps JSONB,                   -- 턴바이턴 안내
    
    FOREIGN KEY (route_day_id) REFERENCES route_days(id) ON DELETE CASCADE
);

-- 인덱스 생성
CREATE INDEX idx_routes_plan_version ON routes(plan_id, version);
CREATE INDEX idx_route_days_route_id ON route_days(route_id, day_number);
CREATE INDEX idx_route_segments_day_order ON route_segments(route_day_id, segment_order);

-- 샘플 데이터 구조 예시
/*
routes 테이블:
┌─────────────────────────────────────────────────────────┐
│ plan_id: "rec_1750831581"                               │
│ version: 4                                              │
│ total_days: 3                                           │
│ departure_location: "홍대입구역"                         │
│ hotel_location: "명동 호텔"                             │
│ total_distance_km: 45.2                                 │
│ total_duration_minutes: 180                             │
└─────────────────────────────────────────────────────────┘

route_days 테이블:
┌─────────────────────────────────────────────────────────┐
│ Day 1: 홍대입구역 → 아침 스팟들 → 점심 스팟들 → 저녁 → 명동호텔   │
│ Day 2: 명동호텔 → 아침 스팟들 → 점심 스팟들 → 저녁 → 명동호텔     │
│ Day 3: 명동호텔 → 아침 스팟들 → 점심 스팟들 → 홍대입구역         │
└─────────────────────────────────────────────────────────┘

route_segments 테이블:
┌─────────────────────────────────────────────────────────┐
│ Day 1, Segment 1: 홍대입구역 → 예술의전당 (15분, 8.2km)      │
│ Day 1, Segment 2: 예술의전당 → 국립현대미술관 (12분, 5.8km)   │
│ Day 1, Segment 3: 국립현대미술관 → 천상가옥 (20분, 12.1km)   │
│ ...                                                     │
└─────────────────────────────────────────────────────────┘
*/ 