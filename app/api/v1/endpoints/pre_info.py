from fastapi import APIRouter, status

from app.schemas.pre_info import PreInfoRequest, PreInfoResponse

router = APIRouter()


@router.post(
    "/register", response_model=PreInfoResponse, status_code=status.HTTP_201_CREATED
)
async def register_pre_info(
    input_data: PreInfoRequest,
) -> PreInfoResponse:
    """
    行きたい旅行先の事前情報を入力して保存
    """
    # TODO: pre_infoからスポット情報を生成するロジックを実装
    return PreInfoResponse(pre_info_id="pre_info_id")
