import { CommonModule, DatePipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';

import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ApiClient } from '../../core/api-client';
import { RunSummary, Session } from '../../core/types';

@Component({
  selector: 'app-run-explorer',
  standalone: true,
  imports: [
    CommonModule,
    DatePipe,
    FormsModule,
    RouterLink,
    MatCardModule,
    MatFormFieldModule,
    MatSelectModule,
    MatInputModule,
    MatTableModule,
    MatPaginatorModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatTooltipModule,
  ],
  templateUrl: './run-explorer.component.html',
  styleUrl: './run-explorer.component.scss',
})
export class RunExplorerComponent implements OnInit {
  loading = false;
  error: string | null = null;

  sessions: Session[] = [];

  runs: RunSummary[] = [];
  total = 0;
  page = 1;
  pageSize = 25;

  qcPassRate: number | null = null;
  qcStatsText: string | null = null;

  selectedSessionId: number | null = null;
  selectedState: string | null = null;
  searchText = '';

  displayedColumns: string[] = [
    'run_number',
    'run_name',
    'session_id',
    'ts_start',
    'duration',
    'state',
    'qc_status',
    'sample_count',
    'actions',
  ];

  constructor(private readonly api: ApiClient) {}

  ngOnInit(): void {
    this.loadSessions();
    this.loadRuns();
  }

  loadSessions(): void {
    this.api.listSessions().subscribe({
      next: (res) => (this.sessions = res.sessions),
      error: (e) => console.error('Failed to load sessions', e),
    });
  }

  loadRuns(): void {
    this.loading = true;
    this.error = null;
    this.api
      .listRuns({
        sessionId: this.selectedSessionId ?? undefined,
        state: this.selectedState ?? undefined,
        page: this.page,
        pageSize: this.pageSize,
      })
      .subscribe({
        next: (res) => {
          this.runs = res.runs;
          this.total = res.total;
          this.page = res.page;
          this.pageSize = res.page_size;
          if (res.qc_stats) {
            this.qcPassRate = res.qc_stats.pass_rate;
            this.qcStatsText = `${res.qc_stats.passed}/${res.qc_stats.total_runs} pass`;
          } else {
            this.qcPassRate = null;
            this.qcStatsText = null;
          }
          this.loading = false;
        },
        error: (e) => {
          console.error(e);
          this.loading = false;
          this.error = 'Failed to load runs. Is the API running on :8000?';
        },
      });
  }

  visibleRuns(): RunSummary[] {
    const q = this.searchText.trim().toLowerCase();
    if (!q) return this.runs;
    return this.runs.filter((r) => {
      const hay = `${r.run_id} ${r.run_number} ${r.run_name} ${r.state} ${r.qc_status ?? ''} ${r.session_id ?? ''}`.toLowerCase();
      return hay.includes(q);
    });
  }

  onFiltersChanged(): void {
    this.page = 1;
    this.loadRuns();
  }

  onPage(event: PageEvent): void {
    this.page = event.pageIndex + 1;
    this.pageSize = event.pageSize;
    this.loadRuns();
  }

  formatDuration(run: RunSummary): string {
    if (!run.ts_start || !run.ts_end) return '-';
    const s = new Date(run.ts_start).getTime();
    const e = new Date(run.ts_end).getTime();
    if (!Number.isFinite(s) || !Number.isFinite(e) || e < s) return '-';
    const sec = Math.round((e - s) / 1000);
    return `${sec}s`;
  }

  badgeClass(status: string | null | undefined): string {
    const s = (status ?? '').toLowerCase();
    if (s === 'pass') return 'qc-pass';
    if (s === 'warn') return 'qc-warn';
    if (s === 'fail') return 'qc-fail';
    return 'qc-pending';
  }
}


