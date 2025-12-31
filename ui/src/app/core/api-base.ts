export function getApiBaseUrl(): string {
  const w = window as any;
  const configured = w?.__AEROSTREAM_API_BASE__ as string | undefined;
  if (configured !== undefined && configured !== null) return String(configured);

  const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
  return isLocal ? 'http://localhost:8000' : '';
}


