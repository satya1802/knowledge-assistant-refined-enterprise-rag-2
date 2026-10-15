"""Settings router: view and update application settings (admin only).

Every route is a stub that raises 501 until a development ticket implements
it. The ``response_model`` on each route declares the agreed contract so the
OpenAPI document the frontend is built against is complete from day one.
"""

from fastapi import APIRouter, HTTPException

from app.schemas import SettingsResponse, SettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings() -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.patch("", response_model=SettingsResponse)
async def update_settings(request: SettingsUpdateRequest) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
