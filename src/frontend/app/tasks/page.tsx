'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  createTask,
  fetchDefaultProject,
  fetchProjects,
  fetchTasks,
  ProjectRecord,
  TaskRecord,
  TaskRequest,
} from '@/lib/api';

function StatusBadge({ status }: { status: string }) {
  const className = `status-badge status-${status.toLowerCase().replace(/_/g, '-')}`;
  return <span className={className}>{status.replace(/_/g, ' ')}</span>;
}

function TaskCreateForm({
  onClose,
  onCreated,
  projects,
  initialProjectId,
}: {
  onClose: () => void;
  onCreated: () => void;
  projects: ProjectRecord[];
  initialProjectId: string;
}) {
  const [goal, setGoal] = useState('');
  const [repos, setRepos] = useState('');
  const [maxRounds, setMaxRounds] = useState('2');
  const [agentProvider, setAgentProvider] = useState('');
  const [projectId, setProjectId] = useState(initialProjectId);
  const [customInstructions, setCustomInstructions] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const selected = projects.find((project) => project.id === projectId);
    if (!selected || repos.trim()) {
      return;
    }
    if (selected.default_repos.length > 0) {
      setRepos(selected.default_repos.join('\n'));
    }
  }, [projectId, projects, repos]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const request: TaskRequest = {
        goal,
        repos: repos
          .split('\n')
          .map((repo) => repo.trim())
          .filter((repo) => repo.length > 0),
        max_rounds: parseInt(maxRounds, 10),
        agent_provider: agentProvider || undefined,
        project_id: projectId || undefined,
        custom_instructions: customInstructions.trim() || undefined,
      };
      await createTask(request);
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create task');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Create task">
      <div className="modal-panel">
        <div className="modal-head">
          <h2 className="section-title">Create New Task</h2>
          <p className="section-subtitle">
            Define the objective, repositories, and execution bounds for this run.
          </p>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="field-block">
            <label className="field-label">Goal</label>
            <textarea
              className="field-input field-textarea"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              required
              rows={3}
              placeholder="Enter task goal..."
            />
          </div>
          <div className="field-block">
            <label className="field-label">Repositories (one per line)</label>
            <textarea
              className="field-input field-textarea"
              value={repos}
              onChange={(e) => setRepos(e.target.value)}
              required
              rows={4}
              placeholder="repo1&#10;repo2&#10;repo3"
            />
          </div>
          <div className="form-grid">
            <div>
              <label className="field-label">Max Rounds</label>
              <input
                type="number"
                className="field-input"
                value={maxRounds}
                onChange={(e) => setMaxRounds(e.target.value)}
                required
                min="1"
              />
            </div>
            <div>
              <label className="field-label">Agent Provider (optional)</label>
              <select
                className="field-input"
                value={agentProvider}
                onChange={(e) => setAgentProvider(e.target.value)}
              >
                <option value="">Default</option>
                <option value="codex">Codex</option>
                <option value="copilot">Copilot</option>
              </select>
            </div>
          </div>
          <div className="field-block">
            <label className="field-label">Project</label>
            <select
              className="field-input"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              required
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field-block">
            <label className="field-label">Custom Instructions (optional)</label>
            <textarea
              className="field-input field-textarea"
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
              rows={3}
              placeholder="Any project/task-specific guidance for planning."
            />
          </div>
          {error && (
            <div className="error-callout small-callout">{error}</div>
          )}
          <div className="modal-actions">
            <button
              type="button"
              onClick={onClose}
              className="secondary-button"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="primary-button"
              disabled={loading}
            >
              {loading ? 'Creating...' : 'Create Task'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const STATUS_OPTIONS = [
  'PENDING',
  'CLAIMED',
  'RUNNING',
  'SUCCEEDED',
  'FAILED',
  'HITL_REQUIRED',
  'CANCELLED',
];
const PAGE_SIZE = 20;

export default function TasksPage() {
  const searchParams = useSearchParams();
  const projectFromQuery = searchParams.get('projectId') || '';
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [defaultProjectId, setDefaultProjectId] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrev, setHasPrev] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchTasks({
        status: statusFilter || undefined,
        page,
        pageSize: PAGE_SIZE,
        projectId: selectedProjectId || undefined,
      });
      const maybeItems = (data as unknown as { items?: TaskRecord[] }).items;
      const fallbackItems = Array.isArray(data as unknown) ? (data as unknown as TaskRecord[]) : [];
      const items = Array.isArray(maybeItems) ? maybeItems : fallbackItems;

      setTasks(items);
      setTotal(
        typeof (data as { total?: unknown }).total === 'number'
          ? (data as { total: number }).total
          : items.length,
      );
      setHasNext(Boolean((data as { has_next?: unknown }).has_next));
      setHasPrev(Boolean((data as { has_prev?: unknown }).has_prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tasks');
    } finally {
      setLoading(false);
    }
  }, [page, selectedProjectId, statusFilter]);

  const loadProjects = useCallback(async () => {
    try {
      const [projectItems, defaultProject] = await Promise.all([
        fetchProjects(),
        fetchDefaultProject(),
      ]);
      setProjects(projectItems);
      setDefaultProjectId(defaultProject.id);
      setSelectedProjectId((current) => current || projectFromQuery || defaultProject.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    }
  }, [projectFromQuery]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  useEffect(() => {
    if (!projectFromQuery || projects.length === 0) {
      return;
    }
    const match = projects.find((project) => project.id === projectFromQuery);
    if (match) {
      setSelectedProjectId(projectFromQuery);
      setPage(1);
    }
  }, [projectFromQuery, projects]);

  const summary = useMemo(() => {
    const counts = tasks.reduce<Record<string, number>>((acc, task) => {
      const key = task.status;
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});

    const active =
      (counts.PENDING || 0) + (counts.CLAIMED || 0) + (counts.RUNNING || 0) + (counts.HITL_REQUIRED || 0);

    return {
      total,
      active,
      succeeded: counts.SUCCEEDED || 0,
      failed: counts.FAILED || 0,
    };
  }, [tasks, total]);

  const paginationLabel = useMemo(() => {
    if (total === 0 || tasks.length === 0) {
      return 'Showing 0 tasks';
    }
    const start = (page - 1) * PAGE_SIZE + 1;
    const end = start + tasks.length - 1;
    return `Showing ${start}-${end} of ${total}`;
  }, [page, tasks.length, total]);

  const canCreateTask = projects.length > 0 && defaultProjectId.length > 0;
  const projectNameById = useMemo(() => {
    return projects.reduce<Record<string, string>>((acc, project) => {
      acc[project.id] = project.name;
      return acc;
    }, {});
  }, [projects]);
  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) || null,
    [projects, selectedProjectId],
  );

  const handleTaskCreated = useCallback(() => {
    if (page === 1) {
      void loadTasks();
      return;
    }
    setPage(1);
  }, [loadTasks, page]);

  return (
    <div className="page-stack">
      <section className="panel panel-hero">
        <div>
          <p className="eyebrow">Coordination</p>
          <h1 className="page-title">Task Control Center</h1>
          <p className="page-subtitle">
            Launch, monitor, and resolve multi-repository workflows with high signal and clear status.
          </p>
          {selectedProject && (
            <p className="helper-text">Current project: {selectedProject.name}</p>
          )}
        </div>
        <div className="hero-actions">
          <Link href="/projects" className="secondary-button">
            Manage Projects
          </Link>
          <button
            onClick={() => setShowCreateForm(true)}
            className="primary-button"
            disabled={!canCreateTask}
          >
            New Task
          </button>
        </div>
      </section>

      <section className="stats-grid stagger-list">
        <article className="metric-card">
          <span>Total</span>
          <strong>{summary.total}</strong>
        </article>
        <article className="metric-card">
          <span>Active</span>
          <strong>{summary.active}</strong>
        </article>
        <article className="metric-card">
          <span>Succeeded</span>
          <strong>{summary.succeeded}</strong>
        </article>
        <article className="metric-card">
          <span>Failed</span>
          <strong>{summary.failed}</strong>
        </article>
      </section>

      <section className="panel panel-soft controls-bar">
        <label className="field-label" htmlFor="project-filter">
          Project
        </label>
        <select
          id="project-filter"
          className="field-input filter-select"
          value={selectedProjectId}
          onChange={(e) => {
            setSelectedProjectId(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All projects</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        <label className="field-label" htmlFor="status-filter">
          Filter by Status
        </label>
        <select
          id="status-filter"
          className="field-input filter-select"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All</option>
          {STATUS_OPTIONS.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
        <button type="button" className="secondary-button" onClick={loadTasks}>
          Refresh
        </button>
      </section>

      {error && <div className="error-callout">{error}</div>}

      {loading ? (
        <div className="panel callout">Loading tasks...</div>
      ) : tasks.length === 0 ? (
        <div className="panel callout">No tasks found for the selected filter.</div>
      ) : (
        <section className="panel table-panel">
          <div className="table-wrap">
            <table className="tasks-table">
              <thead>
                <tr>
                  <th>Project</th>
                  <th>ID</th>
                  <th>Goal</th>
                  <th>Status</th>
                  <th>Attempts</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id} className="task-row">
                    <td>
                      <span>{projectNameById[task.project_id] || task.project_id.slice(0, 8)}</span>
                    </td>
                    <td>
                      <Link href={`/tasks/${task.id}`} className="task-link">
                        {task.id.substring(0, 8)}...
                      </Link>
                    </td>
                    <td className="goal-cell">
                      {task.request.goal.substring(0, 80)}
                      {task.request.goal.length > 80 ? '...' : ''}
                    </td>
                    <td>
                      <StatusBadge status={task.status} />
                    </td>
                    <td>{task.attempts}</td>
                    <td>{new Date(task.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination-row">
            <p className="helper-text pagination-label">{paginationLabel}</p>
            <div className="pagination-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={!hasPrev}
              >
                Previous
              </button>
              <span className="pagination-page">Page {page}</span>
              <button
                type="button"
                className="secondary-button"
                onClick={() => setPage((current) => current + 1)}
                disabled={!hasNext}
              >
                Next
              </button>
            </div>
          </div>
        </section>
      )}

      {showCreateForm && canCreateTask && (
        <TaskCreateForm
          onClose={() => setShowCreateForm(false)}
          onCreated={handleTaskCreated}
          projects={projects}
          initialProjectId={selectedProjectId || defaultProjectId}
        />
      )}
    </div>
  );
}
