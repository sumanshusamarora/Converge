const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080';

export type TaskRequest = {
  goal: string;
  repos: string[];
  max_rounds?: number;
  agent_provider?: string;
  project_id?: string;
  custom_instructions?: string;
  execute_immediately?: boolean;
  metadata?: Record<string, unknown>;
};

export type TaskRecord = {
  id: string;
  project_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  attempts: number;
  request: TaskRequest;
  last_error?: string | null;
  artifacts_dir?: string | null;
  hitl_questions?: string[];
  status_reason?: string | null;
};

export type PaginatedTasksResponse = {
  items: TaskRecord[];
  total: number;
  page: number;
  page_size: number;
  offset: number;
  has_next: boolean;
  has_prev: boolean;
};

export type ProjectPreferences = {
  planning_strategy: 'extend_existing' | 'best_practice_first';
  hitl_trigger_mode: 'blockers_only' | 'strict';
  max_hitl_questions: number;
  execution_flow: 'plan_then_execute' | 'plan_and_execute';
  allow_custom_instructions_after_plan: boolean;
  enforce_existing_patterns: boolean;
  prefer_minimal_changes: boolean;
  require_best_practice_alignment: boolean;
  prompt_preamble?: string | null;
};

export type ProjectRecord = {
  id: string;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
  default_repos: string[];
  default_instructions?: string | null;
  preferences: ProjectPreferences;
};

export type ProjectCreateRequest = {
  name: string;
  description?: string;
  default_repos?: string[];
  default_instructions?: string;
  preferences?: Partial<ProjectPreferences>;
};

export type ProjectUpdateRequest = {
  name?: string;
  description?: string | null;
  default_repos?: string[];
  default_instructions?: string | null;
  preferences?: ProjectPreferences;
};

export type HitlQuestion = {
  id: string;
  text: string;
  options?: string[];
  default?: string;
};

export type HitlPayload = {
  questions: HitlQuestion[];
  notes?: string;
};

export type TaskEvent = {
  id: string;
  ts: string;
  type:
    | 'TASK_CREATED'
    | 'TASK_CLAIMED'
    | 'PLANNING_STARTED'
    | 'PROPOSAL_GENERATED'
    | 'ROUND_STARTED'
    | 'HITL_REQUIRED'
    | 'HITL_RESOLVED'
    | 'EXECUTION_STARTED'
    | 'EXECUTION_FINISHED'
    | 'ARTIFACTS_WRITTEN'
    | 'TASK_SUCCEEDED'
    | 'TASK_FAILED';
  title: string;
  status: 'info' | 'success' | 'warning' | 'error';
  details: Record<string, unknown>;
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

export type FetchTasksParams = {
  status?: string;
  page?: number;
  pageSize?: number;
  projectId?: string;
};

export async function fetchTasks(params: FetchTasksParams = {}): Promise<PaginatedTasksResponse> {
  const searchParams = new URLSearchParams();
  if (params.status) {
    searchParams.set('status', params.status);
  }
  if (params.page) {
    searchParams.set('page', String(params.page));
  }
  if (params.pageSize) {
    searchParams.set('page_size', String(params.pageSize));
  }
  if (params.projectId) {
    searchParams.set('project_id', params.projectId);
  }
  const query = searchParams.toString();
  const response = await fetch(
    `${API_BASE}/api/tasks${query ? `?${query}` : ''}`,
    { cache: 'no-store' },
  );
  return handleResponse<PaginatedTasksResponse>(response);
}

export async function fetchTask(taskId: string): Promise<TaskRecord> {
  const response = await fetch(`${API_BASE}/api/tasks/${taskId}`, { cache: 'no-store' });
  return handleResponse<TaskRecord>(response);
}

export async function fetchTaskEvents(taskId: string): Promise<TaskEvent[]> {
  const response = await fetch(`${API_BASE}/api/tasks/${taskId}/events`, { cache: 'no-store' });
  return handleResponse<TaskEvent[]>(response);
}

export async function createTask(request: TaskRequest): Promise<TaskRecord> {
  const response = await fetch(`${API_BASE}/api/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<TaskRecord>(response);
}

export async function createFollowupTask(
  taskId: string,
  instruction: string,
  executeImmediately = false,
): Promise<TaskRecord> {
  const response = await fetch(`${API_BASE}/api/tasks/${taskId}/followup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      instruction,
      execute_immediately: executeImmediately,
    }),
  });
  return handleResponse<TaskRecord>(response);
}

export async function fetchProjects(): Promise<ProjectRecord[]> {
  const response = await fetch(`${API_BASE}/api/projects`, { cache: 'no-store' });
  const data = await handleResponse<{ items: ProjectRecord[] }>(response);
  return data.items;
}

export async function fetchDefaultProject(): Promise<ProjectRecord> {
  const response = await fetch(`${API_BASE}/api/projects/default`, { cache: 'no-store' });
  return handleResponse<ProjectRecord>(response);
}

export async function fetchProject(projectId: string): Promise<ProjectRecord> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}`, { cache: 'no-store' });
  return handleResponse<ProjectRecord>(response);
}

export async function createProject(request: ProjectCreateRequest): Promise<ProjectRecord> {
  const response = await fetch(`${API_BASE}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<ProjectRecord>(response);
}

export async function updateProject(
  projectId: string,
  request: ProjectUpdateRequest,
): Promise<ProjectRecord> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<ProjectRecord>(response);
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
  const response = await fetch(
    `${API_BASE}/api/runs/${runId}/files/${encodeURI(filePath)}`,
    { cache: 'no-store' },
  );
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.text();
}

export function getRunFileUrl(runId: string, filePath: string): string {
  return `${API_BASE}/api/runs/${runId}/files/${encodeURI(filePath)}`;
}
