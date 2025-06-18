from fastapi import APIRouter, status

from app.schemas.pre_info import (
    PreInfoRequest, PreInfoResponse
)

router = APIRouter()

@router.post("/pre_info", response_model=PreInfoResponse, status_code=status.HTTP_201_CREATED)
async def pre_info(
    input_data: PreInfoRequest,
) -> PreInfoResponse:
    """
    pre_infoからスポット情報を生成するエンドポイント
    """
    # TODO: pre_infoからスポット情報を生成するロジックを実装
    return PreInfoResponse(pre_info_id="pre_info_id")