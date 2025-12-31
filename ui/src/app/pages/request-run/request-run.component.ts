import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { ApiClient } from '../../core/api-client';
import { DemoRequest } from '../../core/types';

@Component({
  selector: 'app-request-run',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
  ],
  templateUrl: './request-run.component.html',
  styleUrl: './request-run.component.scss',
})
export class RequestRunComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ApiClient);

  submitting = false;
  statusLoading = false;
  created: { request_id: number; status: string } | null = null;
  status: DemoRequest | null = null;
  error: string | null = null;

  form = this.fb.group({
    requester_name: [''],
    requester_email: [''],
    requested_variant: ['baseline', Validators.required],
    requested_duration_sec: [5, [Validators.required, Validators.min(1), Validators.max(30)]],
    requested_speed_ms: [50, [Validators.required, Validators.min(5), Validators.max(80)]],
    requested_aoa_deg: [0, [Validators.required, Validators.min(-10), Validators.max(10)]],
    requested_yaw_deg: [0, [Validators.required, Validators.min(-15), Validators.max(15)]],
    requested_notes: [''],
  });

  checkForm = this.fb.group({
    request_id: [null as number | null, [Validators.required]],
  });

  submit(): void {
    if (this.form.invalid) return;
    this.submitting = true;
    this.error = null;
    this.created = null;

    const v = this.form.getRawValue();
    this.api.createDemoRequest({
      requester_name: v.requester_name || null,
      requester_email: v.requester_email || null,
      requested_variant: v.requested_variant as any,
      requested_duration_sec: Number(v.requested_duration_sec),
      requested_speed_ms: Number(v.requested_speed_ms),
      requested_aoa_deg: Number(v.requested_aoa_deg),
      requested_yaw_deg: Number(v.requested_yaw_deg),
      requested_notes: v.requested_notes || null,
    }).subscribe({
      next: (res) => {
        this.created = res;
        this.checkForm.patchValue({ request_id: res.request_id });
        this.submitting = false;
      },
      error: (e) => {
        console.error(e);
        this.submitting = false;
        this.error = 'Failed to submit request (API not reachable?)';
      },
    });
  }

  loadStatus(): void {
    if (this.checkForm.invalid) return;
    const id = Number(this.checkForm.value.request_id);
    this.statusLoading = true;
    this.error = null;
    this.status = null;
    this.api.getDemoRequest(id).subscribe({
      next: (res) => {
        this.status = res;
        this.statusLoading = false;
      },
      error: (e) => {
        console.error(e);
        this.statusLoading = false;
        this.error = `Request ${id} not found (or API error).`;
      },
    });
  }
}


