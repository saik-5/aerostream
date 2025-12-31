export type QcStatus = 'pass' | 'warn' | 'fail' | 'not_run' | string;

export interface QcStats {
  total_runs: number;
  passed: number;
  warned: number;
  failed: number;
  not_run: number;
  pass_rate: number;
}

export interface RunSummary {
  run_id: number;
  run_number: number;
  run_name: string;
  session_id?: number | null;
  state: string;
  run_type?: string | null;
  ts_start?: string | null;
  ts_end?: string | null;
  sample_count: number;
  qc_status?: QcStatus | null;
}

export interface RunListResponse {
  runs: RunSummary[];
  total: number;
  page: number;
  page_size: number;
  qc_stats?: QcStats | null;
}

export interface RunDetail {
  run_id: number;
  run_number: number;
  run_name: string;
  session_id?: number | null;
  state: string;
  run_type?: string | null;
  ts_start?: string | null;
  ts_end?: string | null;
  duration_seconds?: number | null;
  sample_count: number;
  velocity_setpoint?: number | null;
  aoa_setpoint?: number | null;
  yaw_setpoint?: number | null;
  roll_setpoint?: number | null;
  ride_height_front?: number | null;
  ride_height_rear?: number | null;
  notes?: string | null;
}

export interface Session {
  session_id: number;
  session_name: string;
  model_id: number;
  model_name?: string | null;
  test_cell_id: number;
  test_cell_name?: string | null;
  ts_start?: string | null;
  ts_end?: string | null;
  run_count: number;
  notes?: string | null;
}

export interface SessionListResponse {
  sessions: Session[];
  total: number;
}

export interface Channel {
  channel_id: number;
  channel_code: string;
  channel_name: string;
  category: string;
  units: string;
  sample_rate_hz: number;
}

export interface ChannelListResponse {
  channels: Channel[];
  total: number;
}

export interface DataPoint {
  ts: string;
  value: number;
  min_value?: number | null;
  max_value?: number | null;
  sample_count?: number | null;
}

export interface ChannelData {
  channel_id: number;
  channel_code?: string | null;
  data: DataPoint[];
}

export interface RunDataResponse {
  run_id: number;
  channels: ChannelData[];
  bucket_seconds: number;
  total_points: number;
}

export interface QcCheck {
  rule_code: string;
  rule_name: string;
  status: string;
  measured_value?: number | null;
  threshold?: number | null;
  details: string;
  channel_id?: number | null;
}

export interface QcReport {
  run_id: number;
  overall_status: string;
  total_checks: number;
  passed_checks: number;
  warning_checks: number;
  failed_checks: number;
  checks: QcCheck[];
  critical_issues: string[];
  recommendations: string[];
}

export interface RunStatistics {
  run_id: number;
  total_samples: number;
  valid_samples: number;
  spike_count: number;
  cl_mean?: number | null;
  cl_std?: number | null;
  cd_mean?: number | null;
  cd_std?: number | null;
  efficiency?: number | null;
  aero_balance_pct?: number | null;
}

export interface CompareRequest {
  baseline_run_id: number;
  variant_run_id: number;
  channel_ids?: number[] | null;
}

export interface DeltaMetric {
  metric: string;
  baseline_value: number;
  variant_value: number;
  delta: number;
  delta_pct: number;
}

export interface CompareResponse {
  baseline_run_id: number;
  variant_run_id: number;
  deltas: DeltaMetric[];
  summary: string;
}

export interface DemoRequestCreate {
  requester_name?: string | null;
  requester_email?: string | null;
  requested_variant: 'baseline' | 'variant_a' | 'variant_b';
  requested_duration_sec: number;
  requested_speed_ms: number;
  requested_aoa_deg: number;
  requested_yaw_deg: number;
  requested_notes?: string | null;
}

export interface DemoRequest {
  request_id: number;
  requester_name?: string | null;
  requester_email?: string | null;
  requested_variant: string;
  requested_duration_sec: number;
  requested_speed_ms: number;
  requested_aoa_deg: number;
  requested_yaw_deg: number;
  requested_notes?: string | null;
  status: string;
  reviewer_notes?: string | null;
  run_id?: number | null;
  created_at?: string | null;
  reviewed_at?: string | null;
}


