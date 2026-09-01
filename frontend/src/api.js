// API Client Wrapper for Revenue Recovery Engine

const API_BASE = window.location.origin.includes(':8000') 
  ? '' 
  : 'http://127.0.0.1:8000';

export async function runBatch(seed = 42, eventCount = 70) {
  const response = await fetch(`${API_BASE}/batch/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ seed: Number(seed), event_count: Number(eventCount) })
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || 'Failed to execute batch run');
  }

  return response.json();
}

export async function getBatch(batchId) {
  const response = await fetch(`${API_BASE}/batch/${batchId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch batch ${batchId}`);
  }
  return response.json();
}

export async function getEventTrace(batchId, eventId) {
  const response = await fetch(`${API_BASE}/batch/${batchId}/events/${eventId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch event trace for ${eventId}`);
  }
  return response.json();
}

export function getExportUrl(batchId, format = 'csv') {
  return `${API_BASE}/batch/${batchId}/export?format=${format}`;
}
