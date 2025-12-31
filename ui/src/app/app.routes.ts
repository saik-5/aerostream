import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'runs' },

  {
    path: 'runs',
    loadComponent: () => import('./pages/run-explorer/run-explorer.component').then(m => m.RunExplorerComponent),
  },
  {
    path: 'runs/:runId',
    loadComponent: () => import('./pages/run-detail/run-detail.component').then(m => m.RunDetailComponent),
  },
  {
    path: 'compare',
    loadComponent: () => import('./pages/compare/compare.component').then(m => m.CompareComponent),
  },
  {
    path: 'qc',
    loadComponent: () => import('./pages/qc/qc.component').then(m => m.QcComponent),
  },
  {
    path: 'request',
    loadComponent: () => import('./pages/request-run/request-run.component').then(m => m.RequestRunComponent),
  },

  { path: '**', redirectTo: 'runs' },
];
