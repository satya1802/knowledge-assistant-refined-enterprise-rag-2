"""Auth router: login, logout, profile, and password management.

Every route is a stub that raises 501 until a development ticket implements
it. The ``response_model`` on each route declares the agreed contract so the
OpenAPI document the frontend is built against is complete from day one.
"""

from fastapi import APIRouter, HTTPException

from app.schemas import ChangePasswordRequest, LoginRequest, MessageResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserResponse)
async def login(request: LoginRequest) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/logout", response_model=MessageResponse)
async def logout() -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/me", response_model=UserResponse)
async def me() -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(request: ChangePasswordRequest) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
