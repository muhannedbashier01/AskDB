import type { QueryResponse, SchemaResponse, HealthResponse } from '../types';

const API_BASE = '/api/v1';

export async function submitQuery(query: string, sessionId?: string): Promise<QueryResponse> {
  const body: Record<string, string> = { query };
  if (sessionId) {
    body.session_id = sessionId;
  }

  const response = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function clearSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/session/${sessionId}`, { method: 'DELETE' });
}

export async function getSchema(): Promise<SchemaResponse> {
  const response = await fetch(`${API_BASE}/schema`);

  if (!response.ok) {
    throw new Error(`Failed to fetch schema: HTTP ${response.status}`);
  }

  return response.json();
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`);

  if (!response.ok) {
    throw new Error(`Health check failed: HTTP ${response.status}`);
  }

  return response.json();
}
