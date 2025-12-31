import { CommonModule } from '@angular/common';
import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnChanges,
  SimpleChanges,
  ViewChild,
} from '@angular/core';

import * as d3 from 'd3';

import { ChannelData } from '../../core/types';

@Component({
  selector: 'app-time-series-chart',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './time-series-chart.component.html',
  styleUrl: './time-series-chart.component.scss',
})
export class TimeSeriesChartComponent implements AfterViewInit, OnChanges {
  @Input() channels: ChannelData[] = [];
  @Input() height = 420;

  @ViewChild('host', { static: true }) host!: ElementRef<HTMLDivElement>;

  private initialized = false;

  ngAfterViewInit(): void {
    this.initialized = true;
    this.render();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!this.initialized) return;
    if (changes['channels'] || changes['height']) this.render();
  }

  private render(): void {
    const el = this.host.nativeElement;
    const width = el.clientWidth || 900;
    const height = this.height;

    el.innerHTML = '';

    if (!this.channels || this.channels.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty';
      empty.textContent = 'Select channels to plot';
      el.appendChild(empty);
      return;
    }

    const margin = { top: 18, right: 18, bottom: 30, left: 56 };
    const innerW = Math.max(200, width - margin.left - margin.right);
    const innerH = Math.max(120, height - margin.top - margin.bottom);

    const svg = d3
      .select(el)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', `0 0 ${width} ${height}`);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const allPoints = this.channels.flatMap((c) =>
      c.data.map((p) => ({
        t: new Date(p.ts),
        v: p.value,
      }))
    );

    const tExtent = d3.extent(allPoints, (d) => d.t) as [Date, Date];
    const vExtent = d3.extent(allPoints, (d) => d.v) as [number, number];

    const x = d3.scaleTime().domain(tExtent).range([0, innerW]);
    const y = d3
      .scaleLinear()
      .domain([vExtent[0] ?? 0, vExtent[1] ?? 1])
      .nice()
      .range([innerH, 0]);

    // Grid
    g.append('g')
      .attr('class', 'grid')
      .call(d3.axisLeft(y).ticks(5).tickSize(-innerW).tickFormat(() => ''))
      .selectAll('line')
      .attr('opacity', 0.15);

    // Axes
    g.append('g').attr('transform', `translate(0,${innerH})`).call(d3.axisBottom(x).ticks(6));
    g.append('g').call(d3.axisLeft(y).ticks(6));

    const palette = [
      '#58A6FF',
      '#F78166',
      '#3FB950',
      '#D29922',
      '#A371F7',
      '#79C0FF',
      '#FFA657',
      '#56D364',
      '#DB6D28',
      '#BC8CFF',
    ];

    const line = d3
      .line<{ t: Date; v: number }>()
      .x((d) => x(d.t))
      .y((d) => y(d.v));

    this.channels.forEach((ch, idx) => {
      const series = ch.data.map((p) => ({ t: new Date(p.ts), v: p.value }));
      g.append('path')
        .datum(series)
        .attr('fill', 'none')
        .attr('stroke', palette[idx % palette.length])
        .attr('stroke-width', 1.6)
        .attr('opacity', 0.9)
        .attr('d', line as any);
    });
  }
}


