"""Users router: list and create user accounts (admin only).

Every route is a stub that raises 501 until a development ticket implements
it. The ``response_model`` on each route declares the agreed contract so the
OpenAPI document the frontend is built against is complete from day one.
"""

from fastapi import APIRouter, HTTPException

from app.schemas import CreateUserRequest, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users() -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("", response_model=UserResponse)
async def create_user(request: CreateUserRequest) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
