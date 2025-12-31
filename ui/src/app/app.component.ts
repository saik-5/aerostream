import { Component } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';

import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';

import { getApiBaseUrl } from './core/api-base';

@Component({
  selector: 'app-root',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatSidenavModule,
    MatToolbarModule,
    MatListModule,
    MatIconModule,
    MatButtonModule,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent {
  readonly docsUrl = (() => {
    const base = getApiBaseUrl();
    return base ? `${base}/docs` : '/docs';
  })();

  collapsed = false;

  toggleNav(): void {
    this.collapsed = !this.collapsed;
    // Force layout recalculation so content margin matches the new drawer width.
    setTimeout(() => window.dispatchEvent(new Event('resize')), 0);
  }
}
