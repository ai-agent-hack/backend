# VertexAI gRPC 직접 사용 예시
import grpc
from google.auth import default
from google.auth.transport.grpc import secure_authorized_channel
from google.cloud.aiplatform_v1 import PredictionServiceClient
from google.cloud.aiplatform_v1.types import PredictRequest, PredictResponse
from google.protobuf import json_format
import json
from typing import List, Dict, Any


class VertexGRPCService:
    """
    VertexAI gRPC 직접 통신 서비스
    고성능이 필요한 경우 사용
    """

    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.client = self._create_grpc_client()

    def _create_grpc_client(self) -> PredictionServiceClient:
        """gRPC 클라이언트 생성"""
        # 인증 정보 가져오기
        credentials, _ = default()

        # gRPC 채널 생성
        channel = secure_authorized_channel(
            credentials, "aiplatform.googleapis.com:443"
        )

        # Prediction Service 클라이언트 생성
        client = PredictionServiceClient(transport="grpc")
        return client

    async def predict_with_grpc(
        self,
        model_name: str,
        instances: List[Dict[str, Any]],
        parameters: Dict[str, Any] = None,
    ) -> PredictResponse:
        """
        gRPC를 사용한 직접 예측 요청

        Args:
            model_name: 모델 이름 (예: "gemini-2.0-flash")
            instances: 입력 데이터 인스턴스들
            parameters: 모델 파라미터

        Returns:
            예측 결과
        """
        # 엔드포인트 경로 구성
        endpoint = f"projects/{self.project_id}/locations/{self.location}/publishers/google/models/{model_name}"

        # gRPC 요청 구성
        request = PredictRequest(
            endpoint=endpoint,
            instances=[json_format.ParseDict(instance, {}) for instance in instances],
        )

        if parameters:
            request.parameters = json_format.ParseDict(parameters, {})

        # gRPC 호출
        response = self.client.predict(request=request)
        return response

    async def stream_predict_with_grpc(
        self,
        model_name: str,
        instances: List[Dict[str, Any]],
        parameters: Dict[str, Any] = None,
    ):
        """
        gRPC 스트리밍 예측 (향후 지원 시)
        """
        # 현재 VertexAI는 스트리밍 gRPC를 완전히 지원하지 않음
        # 하지만 구조는 다음과 같을 것:
        pass

    def close(self):
        """연결 종료"""
        if hasattr(self.client, "close"):
            self.client.close()


# 성능 비교를 위한 벤치마크 함수
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor


async def benchmark_grpc_vs_rest():
    """gRPC vs REST 성능 비교"""
    project_id = "your-project-id"

    # 테스트 데이터
    test_instances = [
        {"content": {"parts": [{"text": "Hello, world!"}]}},
        {"content": {"parts": [{"text": "How are you?"}]}},
        {"content": {"parts": [{"text": "What is AI?"}]}},
    ]

    # gRPC 서비스
    grpc_service = VertexGRPCService(project_id)

    # REST 서비스 (기존 LLMService)
    from app.services.llm_service import LLMService

    rest_service = LLMService()

    # gRPC 성능 측정
    start_time = time.time()
    for instance in test_instances:
        await grpc_service.predict_with_grpc("gemini-2.5-flash", [instance])
    grpc_time = time.time() - start_time

    # REST 성능 측정 (비교용)
    start_time = time.time()
    for _ in range(len(test_instances)):
        # 기존 REST 호출
        pass
    rest_time = time.time() - start_time

    print(f"gRPC Time: {grpc_time:.2f}s")
    print(f"REST Time: {rest_time:.2f}s")
    print(f"Performance Improvement: {(rest_time - grpc_time) / rest_time * 100:.1f}%")

    grpc_service.close()


# 실제 사용 예시
async def example_usage():
    """gRPC 서비스 사용 예시"""
    service = VertexGRPCService("your-project-id")

    try:
        # 단일 예측
        response = await service.predict_with_grpc(
            model_name="gemini-2.5-flash",
            instances=[{"content": {"parts": [{"text": "Explain quantum computing"}]}}],
            parameters={"temperature": 0.7, "maxOutputTokens": 1024},
        )

        print("gRPC Response:", response)

    finally:
        service.close()


if __name__ == "__main__":
    # 벤치마크 실행
    asyncio.run(benchmark_grpc_vs_rest())

    # 사용 예시 실행
    asyncio.run(example_usage())
