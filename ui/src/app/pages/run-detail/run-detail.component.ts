import { CommonModule, DatePipe } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { FormsModule } from '@angular/forms';

import { MatCardModule } from '@angular/material/card';
import { MatTabsModule } from '@angular/material/tabs';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { ApiClient } from '../../core/api-client';
import { Channel, RunDataResponse, RunDetail, RunStatistics, QcReport } from '../../core/types';
import { TimeSeriesChartComponent } from '../../components/time-series-chart/time-series-chart.component';

@Component({
  selector: 'app-run-detail',
  standalone: true,
  imports: [
    CommonModule,
    DatePipe,
    FormsModule,
    RouterLink,
    MatCardModule,
    MatTabsModule,
    MatFormFieldModule,
    MatSelectModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    TimeSeriesChartComponent,
  ],
  templateUrl: './run-detail.component.html',
  styleUrl: './run-detail.component.scss',
})
export class RunDetailComponent implements OnInit, OnDestroy {
  private sub = new Subscription();

  runId!: number;
  loading = false;
  error: string | null = null;

  run: RunDetail | null = null;
  stats: RunStatistics | null = null;
  qc: QcReport | null = null;

  channels: Channel[] = [];
  channelFilter = '';
  selectedChannelIds: number[] = [];
  bucketSeconds = 1;

  // CSS variable value used by the layout grid to size the channel rail.
  // Computed from the longest channel label (channel_id + channel_name).
  channelRailWidth = '280px';

  series: RunDataResponse | null = null;

  constructor(private readonly route: ActivatedRoute, private readonly api: ApiClient) {}

  ngOnInit(): void {
    this.sub.add(
      this.route.paramMap.subscribe((pm) => {
        const id = Number(pm.get('runId'));
        if (!id) return;
        this.runId = id;
        this.loadAll();
      })
    );
  }

  ngOnDestroy(): void {
    this.sub.unsubscribe();
  }

  loadAll(): void {
    this.loading = true;
    this.error = null;
    this.series = null;

    this.api.getRun(this.runId).subscribe({
      next: (r) => (this.run = r),
      error: (e) => console.error(e),
    });
    this.api.getRunStatistics(this.runId).subscribe({
      next: (s) => (this.stats = s),
      error: (e) => console.error(e),
    });
    this.api.getQcReport(this.runId).subscribe({
      next: (q) => (this.qc = q),
      error: (e) => console.error(e),
    });

    this.api.listChannels().subscribe({
      next: (res) => {
        this.channels = res.channels;

        // Compute a tight-but-safe rail width from the largest channel label.
        // Run after render so fonts/styles are available.
        setTimeout(() => this.computeChannelRailWidth(), 0);

        // Default selection: first 4 channels (safe)
        if (this.selectedChannelIds.length === 0) {
          this.selectedChannelIds = this.channels.slice(0, 4).map((c) => c.channel_id);
          this.loadSeries();
        }
        this.loading = false;
      },
      error: (e) => {
        console.error(e);
        this.loading = false;
        this.error = 'Failed to load channels.';
      },
    });
  }

  private computeChannelRailWidth(): void {
    if (!this.channels || this.channels.length === 0) return;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Approximate the text styling used in the channel list (good enough and stable).
    const nameFont = '600 15px Inter, Roboto, "Helvetica Neue", sans-serif';
    const idFont = '600 14px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';

    const measure = (text: string, font: string) => {
      ctx.font = font;
      return ctx.measureText(text).width;
    };

    const maxNamePx = Math.max(...this.channels.map((c) => measure(c.channel_name ?? '', nameFont)));
    // Worst-case id label: "#72" today, but be safe for more ids
    const idPx = measure('#999', idFont);

    // Add chrome: card padding + button padding + gap + scrollbar buffer
    // Keep this deliberately tight; we want the rail to hug the longest label.
    const chromePx = 18 /* card padding */ + 18 /* button insets */ + 8 /* gap */ + 10 /* scrollbar/breathing */;
    const px = Math.ceil(chromePx + idPx + maxNamePx);

    // Clamp to keep it usable and responsive
    const clamped = Math.max(200, Math.min(px, 320));
    this.channelRailWidth = `${clamped}px`;
  }

  loadSeries(): void {
    const ids = this.selectedChannelIds.slice(0, 10); // API limits to 10 channels in runs/{id}/data
    this.api.getRunData(this.runId, { channelIds: ids, bucketSeconds: this.bucketSeconds }).subscribe({
      next: (res) => (this.series = res),
      error: (e) => {
        console.error(e);
        this.error = 'Failed to load time-series data.';
      },
    });
  }

  toggleChannel(channelId: number): void {
    const idx = this.selectedChannelIds.indexOf(channelId);
    if (idx >= 0) this.selectedChannelIds.splice(idx, 1);
    else this.selectedChannelIds.push(channelId);
    this.selectedChannelIds = [...this.selectedChannelIds];
    this.loadSeries();
  }

  filteredChannels(): Channel[] {
    const q = (this.channelFilter || '').toLowerCase().trim();
    if (!q) return this.channels;
    return this.channels.filter((c) => {
      const hay = `#${c.channel_id} ${c.channel_id} ${c.channel_code} ${c.channel_name} ${c.category}`.toLowerCase();
      return hay.includes(q);
    });
  }
}


