const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080';

export type TaskRequest = {
  goal: string;
  repos: string[];
  max_rounds?: number;
  agent_provider?: string;
  metadata?: Record<string, unknown>;
};

export type TaskRecord = {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  attempts: number;
  request: TaskRequest;
  last_error?: string | null;
  artifacts_dir?: string | null;
  status_reason?: string | null;
};

export type RunFile = { path: string; size: number };

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        message = String(payload.detail);
      }
    } catch {
      // ignore parse errors for non-json responses
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function fetchTasks(status?: string): Promise<TaskRecord[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  const response = await fetch(`${API_BASE}/api/tasks${query}`, { cache: 'no-store' });
  return handleResponse<TaskRecord[]>(response);
}

export async function fetchTask(taskId: string): Promise<TaskRecord> {
  const response = await fetch(`${API_BASE}/api/tasks/${taskId}`, { cache: 'no-store' });
  return handleResponse<TaskRecord>(response);
}

export async function createTask(request: TaskRequest): Promise<TaskRecord> {
  const response = await fetch(`${API_BASE}/api/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<TaskRecord>(response);
}

export async function resolveTask(taskId: string, resolution: Record<string, unknown>): Promise<void> {
  const response = await fetch(`${API_BASE}/api/tasks/${taskId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(resolution),
  });
  await handleResponse<Record<string, string>>(response);
}

export async function cancelTask(taskId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/tasks/${taskId}/cancel`, { method: 'POST' });
  await handleResponse<Record<string, string>>(response);
}

export async function fetchRunFiles(runId: string): Promise<RunFile[]> {
  const response = await fetch(`${API_BASE}/api/runs/${runId}/files`, { cache: 'no-store' });
  const data = await handleResponse<{ run_id: string; files: RunFile[] }>(response);
  return data.files;
}

export async function fetchRunFile(runId: string, filePath: string): Promise<string> {
  const response = await fetch(`${API_BASE}/api/runs/${runId}/files/${filePath}`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.text();
}
