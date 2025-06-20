from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.schemas.pre_info import PreInfoRequest, PreInfoResponse, PreInfoUpdate
from app.services.pre_info import PreInfoService
from app.models.user import User
from app.core.dependencies import (
    get_pre_info_service,
    get_current_user_firebase,
    get_current_user_test,
)
from app.core.exceptions import ValidationError, NotFoundError

router = APIRouter()


@router.post(
    "/register", response_model=PreInfoResponse, status_code=status.HTTP_201_CREATED
)
async def register_pre_info(
    input_data: PreInfoRequest,
    current_user: User = Depends(get_current_user_firebase),
    pre_info_service: PreInfoService = Depends(get_pre_info_service),
) -> PreInfoResponse:
    """
    여행지 사전정보를 등록
    """
    try:
        pre_info = pre_info_service.create_pre_info(input_data, current_user.id)
        return PreInfoResponse.model_validate(pre_info)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )


# 🧪 테스트용 엔드포인트 (Firebase 토큰 불필요)
@router.post(
    "/test/register",
    response_model=PreInfoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_pre_info_test(
    input_data: PreInfoRequest,
    current_user: User = Depends(get_current_user_test),
    pre_info_service: PreInfoService = Depends(get_pre_info_service),
) -> PreInfoResponse:
    """
    여행지 사전정보를 등록 (테스트용 - Firebase 토큰 불필요)
    """
    try:
        pre_info = pre_info_service.create_pre_info(input_data, current_user.id)
        return PreInfoResponse.model_validate(pre_info)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )


@router.get("/", response_model=List[PreInfoResponse])
async def get_my_pre_infos(
    skip: int = Query(0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(100, ge=1, le=1000, description="가져올 항목 수"),
    current_user: User = Depends(get_current_user_firebase),
    pre_info_service: PreInfoService = Depends(get_pre_info_service),
) -> List[PreInfoResponse]:
    """
    내 여행 사전정보 목록 조회
    """
    pre_infos = pre_info_service.get_user_pre_infos(current_user.id, skip, limit)
    return [PreInfoResponse.model_validate(pre_info) for pre_info in pre_infos]


@router.get("/{pre_info_id}", response_model=PreInfoResponse)
async def get_pre_info(
    pre_info_id: int,
    current_user: User = Depends(get_current_user_firebase),
    pre_info_service: PreInfoService = Depends(get_pre_info_service),
) -> PreInfoResponse:
    """
    내 특정 여행 사전정보 조회
    """
    try:
        pre_info = pre_info_service.get_pre_info_by_id(pre_info_id, current_user.id)
        return PreInfoResponse.model_validate(pre_info)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/{pre_info_id}", response_model=PreInfoResponse)
async def update_pre_info(
    pre_info_id: int,
    update_data: PreInfoUpdate,
    current_user: User = Depends(get_current_user_firebase),
    pre_info_service: PreInfoService = Depends(get_pre_info_service),
) -> PreInfoResponse:
    """
    내 여행 사전정보 수정
    """
    try:
        pre_info = pre_info_service.update_pre_info(
            pre_info_id, update_data, current_user.id
        )
        return PreInfoResponse.model_validate(pre_info)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )


@router.delete("/{pre_info_id}", response_model=PreInfoResponse)
async def delete_pre_info(
    pre_info_id: int,
    current_user: User = Depends(get_current_user_firebase),
    pre_info_service: PreInfoService = Depends(get_pre_info_service),
) -> PreInfoResponse:
    """
    내 여행 사전정보 삭제
    """
    try:
        deleted_pre_info = pre_info_service.delete_pre_info(
            pre_info_id, current_user.id
        )
        return PreInfoResponse.model_validate(deleted_pre_info)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
