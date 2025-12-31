"""
Demo Requests Router
====================
Public endpoint for requesting demo runs (no-login flow) + admin endpoints for approval/fulfillment.
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Header, Query

from src.api.schemas import (
    DemoRunRequestCreate,
    DemoRunRequest,
    DemoRunRequestListResponse,
    DemoRunRequestAdminUpdate,
)
from src.db.operations import (
    create_demo_run_request,
    get_demo_run_request,
    list_demo_run_requests,
    update_demo_run_request_status,
    attach_run_to_demo_request,
)


router = APIRouter()


def _require_admin(x_admin_token: Optional[str]) -> None:
    expected = os.getenv("ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=500, detail="ADMIN_TOKEN not configured")
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/requests", response_model=dict)
async def create_request(payload: DemoRunRequestCreate, request: Request):
    """Public: create a demo run request."""
    # Basic allowlist for variants
    if payload.requested_variant not in {"baseline", "variant_a", "variant_b"}:
        raise HTTPException(status_code=400, detail="Invalid requested_variant")

    req_id = create_demo_run_request(
        requester_name=payload.requester_name,
        requester_email=payload.requester_email,
        requested_variant=payload.requested_variant,
        requested_duration_sec=payload.requested_duration_sec,
        requested_speed_ms=payload.requested_speed_ms,
        requested_aoa_deg=payload.requested_aoa_deg,
        requested_yaw_deg=payload.requested_yaw_deg,
        requested_notes=payload.requested_notes,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"request_id": req_id, "status": "pending"}


@router.get("/requests/{request_id}", response_model=DemoRunRequest)
async def get_request(request_id: int):
    """Public: get request status."""
    row = get_demo_run_request(request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    return DemoRunRequest(**row)


@router.get("/requests", response_model=DemoRunRequestListResponse)
async def admin_list_requests(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    x_admin_token: Optional[str] = Header(default=None),
):
    """Admin: list requests."""
    _require_admin(x_admin_token)
    rows = list_demo_run_requests(status=status, limit=limit)
    return DemoRunRequestListResponse(requests=[DemoRunRequest(**r) for r in rows], total=len(rows))


@router.post("/requests/{request_id}/admin", response_model=dict)
async def admin_update_request(
    request_id: int,
    payload: DemoRunRequestAdminUpdate,
    x_admin_token: Optional[str] = Header(default=None),
):
    """
    Admin: approve/reject/mark running/completed and optionally attach a run_id.

    This is intentionally simple:
    - Public users can only create and poll requests
    - Admin (you) decides what to run and when
    """
    _require_admin(x_admin_token)

    existing = get_demo_run_request(request_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Request not found")

    # Update status
    update_demo_run_request_status(request_id, payload.status, payload.reviewer_notes)

    # Optionally attach run_id
    if payload.run_id is not None:
        attach_run_to_demo_request(request_id, payload.run_id)

    return {"ok": True}


