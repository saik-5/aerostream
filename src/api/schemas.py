"""
Pydantic Schemas for API
========================
Request and response models for FastAPI endpoints.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# =============================================================================
# Base Models
# =============================================================================

class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: datetime
    version: str = "2.0"


# =============================================================================
# Channel Models
# =============================================================================

class Channel(BaseModel):
    channel_id: int
    channel_code: str
    channel_name: str
    category: str
    units: str
    sample_rate_hz: int
    
    class Config:
        from_attributes = True


class ChannelListResponse(BaseModel):
    channels: List[Channel]
    total: int


# =============================================================================
# Session Models
# =============================================================================

class Session(BaseModel):
    session_id: int
    session_name: str
    model_id: int
    model_name: Optional[str] = None
    test_cell_id: int
    test_cell_name: Optional[str] = None
    ts_start: Optional[datetime] = None
    ts_end: Optional[datetime] = None
    run_count: int = 0
    notes: Optional[str] = None
    
    model_config = {"protected_namespaces": ()}


class SessionListResponse(BaseModel):
    sessions: List[Session]
    total: int


# =============================================================================
# Run Models
# =============================================================================

class RunSummary(BaseModel):
    """Lightweight run info for list views."""
    run_id: int
    run_number: int
    run_name: str
    session_id: Optional[int] = None
    state: str
    run_type: Optional[str] = None
    ts_start: Optional[datetime] = None
    ts_end: Optional[datetime] = None
    sample_count: int = 0
    qc_status: Optional[str] = None  # From qc_summaries.overall_status
    
    class Config:
        from_attributes = True


class RunDetail(BaseModel):
    """Full run details."""
    run_id: int
    run_number: int
    run_name: str
    session_id: Optional[int] = None
    state: str
    run_type: Optional[str] = None
    ts_start: Optional[datetime] = None
    ts_end: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    sample_count: int = 0
    
    # Setpoints
    velocity_setpoint: Optional[float] = None
    aoa_setpoint: Optional[float] = None
    yaw_setpoint: Optional[float] = None
    roll_setpoint: Optional[float] = None
    ride_height_front: Optional[float] = None
    ride_height_rear: Optional[float] = None
    
    # Notes
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True


class QCStats(BaseModel):
    """QC statistics for dashboard."""
    total_runs: int
    passed: int
    warned: int
    failed: int
    not_run: int
    pass_rate: float  # Percentage 0-100


class RunListResponse(BaseModel):
    runs: List[RunSummary]
    total: int
    page: int = 1
    page_size: int = 50
    qc_stats: Optional[QCStats] = None


# =============================================================================
# Time-Series Data Models
# =============================================================================

class DataPoint(BaseModel):
    ts: datetime
    value: float
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    sample_count: Optional[int] = None


class ChannelData(BaseModel):
    channel_id: int
    channel_code: Optional[str] = None
    data: List[DataPoint]


class RunDataResponse(BaseModel):
    run_id: int
    channels: List[ChannelData]
    bucket_seconds: int
    total_points: int


class RunDataRequest(BaseModel):
    """Query parameters for run data endpoint."""
    channel_ids: Optional[List[int]] = None
    bucket_seconds: int = Field(default=1, ge=1, le=3600)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


# =============================================================================
# QC Models
# =============================================================================

class QCCheck(BaseModel):
    rule_code: str
    rule_name: str
    status: str  # pass, warn, fail, skip
    measured_value: Optional[float] = None
    threshold: Optional[float] = None
    details: str
    channel_id: Optional[int] = None


class QCReport(BaseModel):
    run_id: int
    overall_status: str
    total_checks: int
    passed_checks: int
    warning_checks: int
    failed_checks: int
    checks: List[QCCheck]
    critical_issues: List[str]
    recommendations: List[str]


# =============================================================================
# Statistics Models
# =============================================================================

class RunStatistics(BaseModel):
    run_id: int
    total_samples: int
    valid_samples: int
    spike_count: int
    cl_mean: Optional[float] = None
    cl_std: Optional[float] = None
    cd_mean: Optional[float] = None
    cd_std: Optional[float] = None
    efficiency: Optional[float] = None
    aero_balance_pct: Optional[float] = None


# =============================================================================
# Comparison Models
# =============================================================================

class CompareRequest(BaseModel):
    baseline_run_id: int
    variant_run_id: int
    channel_ids: Optional[List[int]] = None


class DeltaMetric(BaseModel):
    metric: str
    baseline_value: float
    variant_value: float
    delta: float
    delta_pct: float


class CompareResponse(BaseModel):
    baseline_run_id: int
    variant_run_id: int
    deltas: List[DeltaMetric]
    summary: str


# =============================================================================
# Demo run request models (public request queue, admin approval)
# =============================================================================

class DemoRunRequestCreate(BaseModel):
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    requested_variant: str = Field(default="baseline")
    requested_duration_sec: float = Field(default=5.0, ge=1.0, le=30.0)
    requested_speed_ms: float = Field(default=50.0, ge=5.0, le=80.0)
    requested_aoa_deg: float = Field(default=0.0, ge=-10.0, le=10.0)
    requested_yaw_deg: float = Field(default=0.0, ge=-15.0, le=15.0)
    requested_notes: Optional[str] = None


class DemoRunRequest(BaseModel):
    request_id: int
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    requested_variant: str
    requested_duration_sec: float
    requested_speed_ms: float
    requested_aoa_deg: float
    requested_yaw_deg: float
    requested_notes: Optional[str] = None
    status: str
    reviewer_notes: Optional[str] = None
    run_id: Optional[int] = None
    created_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None


class DemoRunRequestListResponse(BaseModel):
    requests: List[DemoRunRequest]
    total: int


class DemoRunRequestAdminUpdate(BaseModel):
    status: str = Field(description="pending/approved/rejected/running/completed/failed")
    reviewer_notes: Optional[str] = None
    run_id: Optional[int] = None
