import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';

import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';

import { ApiClient } from '../../core/api-client';
import { QcReport, RunSummary } from '../../core/types';

@Component({
  selector: 'app-qc',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatTableModule,
  ],
  templateUrl: './qc.component.html',
  styleUrl: './qc.component.scss',
})
export class QcComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ApiClient);

  runs: RunSummary[] = [];
  loading = false;
  error: string | null = null;
  qc: QcReport | null = null;

  form = this.fb.group({
    run_id: [null as number | null, Validators.required],
  });

  displayedColumns = ['status', 'rule_code', 'rule_name', 'channel_id', 'details'];

  ngOnInit(): void {
    this.api.listRuns({ page: 1, pageSize: 100 }).subscribe({
      next: (res) => (this.runs = res.runs),
      error: (e) => console.error(e),
    });
  }

  load(): void {
    if (this.form.invalid) return;
    const runId = Number(this.form.value.run_id);
    this.loading = true;
    this.error = null;
    this.qc = null;
    this.api.getQcReport(runId).subscribe({
      next: (res) => {
        this.qc = res;
        this.loading = false;
      },
      error: (e) => {
        console.error(e);
        this.loading = false;
        this.error = 'Failed to load QC report.';
      },
    });
  }

  badgeClass(status: string): string {
    const s = (status || '').toLowerCase();
    if (s === 'pass') return 'pass';
    if (s === 'warn') return 'warn';
    if (s === 'fail') return 'fail';
    return 'skip';
  }
}


