'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { fetchTasks, createTask, TaskRecord, TaskRequest } from '@/lib/api';

function StatusBadge({ status }: { status: string }) {
  const className = `status-badge status-${status.toLowerCase().replace(/_/g, '-')}`;
  return <span className={className}>{status.replace(/_/g, ' ')}</span>;
}

function TaskCreateForm({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [goal, setGoal] = useState('');
  const [repos, setRepos] = useState('');
  const [maxRounds, setMaxRounds] = useState('2');
  const [agentProvider, setAgentProvider] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchTasks(statusFilter || undefined);
      setTasks(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tasks');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const summary = useMemo(() => {
    const counts = tasks.reduce<Record<string, number>>((acc, task) => {
      const key = task.status;
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});

    const active =
      (counts.PENDING || 0) + (counts.CLAIMED || 0) + (counts.RUNNING || 0) + (counts.HITL_REQUIRED || 0);

    return {
      total: tasks.length,
      active,
      succeeded: counts.SUCCEEDED || 0,
      failed: counts.FAILED || 0,
    };
  }, [tasks]);

  return (
    <div className="page-stack">
      <section className="panel panel-hero">
        <div>
          <p className="eyebrow">Coordination</p>
          <h1 className="page-title">Task Control Center</h1>
          <p className="page-subtitle">
            Launch, monitor, and resolve multi-repository workflows with high signal and clear status.
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="primary-button"
        >
          New Task
        </button>
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
        <label className="field-label" htmlFor="status-filter">
          Filter by Status
        </label>
        <select
          id="status-filter"
          className="field-input filter-select"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
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
        </section>
      )}

      {showCreateForm && (
        <TaskCreateForm
          onClose={() => setShowCreateForm(false)}
          onCreated={loadTasks}
        />
      )}
    </div>
  );
}
