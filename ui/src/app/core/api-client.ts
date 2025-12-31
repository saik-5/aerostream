import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { getApiBaseUrl } from './api-base';
import {
  RunDetail,
  RunListResponse,
  RunDataResponse,
  SessionListResponse,
  ChannelListResponse,
  QcReport,
  RunStatistics,
  CompareRequest,
  CompareResponse,
  DemoRequest,
  DemoRequestCreate,
} from './types';

@Injectable({ providedIn: 'root' })
export class ApiClient {
  private readonly base = getApiBaseUrl();

  constructor(private readonly http: HttpClient) {}

  // Runs
  listRuns(opts: { sessionId?: number; state?: string; page?: number; pageSize?: number } = {}): Observable<RunListResponse> {
    let params = new HttpParams();
    if (opts.sessionId) params = params.set('session_id', String(opts.sessionId));
    if (opts.state) params = params.set('state', String(opts.state));
    params = params.set('page', String(opts.page ?? 1));
    params = params.set('page_size', String(opts.pageSize ?? 50));
    return this.http.get<RunListResponse>(`${this.base}/runs`, { params });
  }

  getRun(runId: number): Observable<RunDetail> {
    return this.http.get<RunDetail>(`${this.base}/runs/${runId}`);
  }

  getRunData(runId: number, opts: { channelIds?: number[]; bucketSeconds?: number } = {}): Observable<RunDataResponse> {
    let params = new HttpParams();
    if (opts.channelIds && opts.channelIds.length > 0) params = params.set('channel_ids', opts.channelIds.join(','));
    params = params.set('bucket_seconds', String(opts.bucketSeconds ?? 1));
    return this.http.get<RunDataResponse>(`${this.base}/runs/${runId}/data`, { params });
  }

  getQcReport(runId: number): Observable<QcReport> {
    return this.http.get<QcReport>(`${this.base}/runs/${runId}/qc`);
  }

  getRunStatistics(runId: number): Observable<RunStatistics> {
    return this.http.get<RunStatistics>(`${this.base}/runs/${runId}/statistics`);
  }

  compareRuns(payload: CompareRequest): Observable<CompareResponse> {
    return this.http.post<CompareResponse>(`${this.base}/runs/compare`, payload);
  }

  // Sessions
  listSessions(): Observable<SessionListResponse> {
    return this.http.get<SessionListResponse>(`${this.base}/sessions`);
  }

  // Channels
  listChannels(): Observable<ChannelListResponse> {
    return this.http.get<ChannelListResponse>(`${this.base}/channels`);
  }

  // Demo requests
  createDemoRequest(payload: DemoRequestCreate): Observable<{ request_id: number; status: string }> {
    return this.http.post<{ request_id: number; status: string }>(`${this.base}/demo/requests`, payload);
  }

  getDemoRequest(requestId: number): Observable<DemoRequest> {
    return this.http.get<DemoRequest>(`${this.base}/demo/requests/${requestId}`);
  }
}


