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
import { CompareResponse, RunSummary } from '../../core/types';

@Component({
  selector: 'app-compare',
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
  templateUrl: './compare.component.html',
  styleUrl: './compare.component.scss',
})
export class CompareComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ApiClient);

  runs: RunSummary[] = [];
  loading = false;
  error: string | null = null;
  result: CompareResponse | null = null;

  form = this.fb.group({
    baseline_run_id: [null as number | null, Validators.required],
    variant_run_id: [null as number | null, Validators.required],
  });

  displayedColumns = ['metric', 'baseline', 'variant', 'delta', 'delta_pct'];

  ngOnInit(): void {
    // Load recent runs for dropdowns
    this.api.listRuns({ page: 1, pageSize: 100 }).subscribe({
      next: (res) => (this.runs = res.runs),
      error: (e) => console.error(e),
    });
  }

  compare(): void {
    if (this.form.invalid) return;
    const baseline = Number(this.form.value.baseline_run_id);
    const variant = Number(this.form.value.variant_run_id);
    this.loading = true;
    this.error = null;
    this.result = null;
    this.api.compareRuns({ baseline_run_id: baseline, variant_run_id: variant }).subscribe({
      next: (res) => {
        this.result = res;
        this.loading = false;
      },
      error: (e) => {
        console.error(e);
        this.loading = false;
        this.error = 'Compare failed. Ensure both runs have statistics computed.';
      },
    });
  }
}


