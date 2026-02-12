'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { fetchTask, resolveTask, cancelTask, fetchRunFiles, fetchRunFile, TaskRecord, RunFile } from '@/lib/api';

function StatusBadge({ status }: { status: string }) {
  const className = `status-badge status-${status.toLowerCase().replace(/_/g, '-')}`;
  return <span className={className}>{status.replace(/_/g, ' ')}</span>;
}

function HITLResolutionForm({ task, onResolved }: { task: TaskRecord; onResolved: () => void }) {
  const [resolution, setResolution] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const questions = task.hitl_questions || [];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const resolutionData = JSON.parse(resolution);
      await resolveTask(task.id, resolutionData);
      onResolved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve task');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="section-title">Resolve HITL Task</h2>
      <p className="section-subtitle">Submit a JSON object with your decision and any supporting notes.</p>
      {questions.length > 0 && (
        <div className="field-block">
          <label className="field-label">Questions to Answer</label>
          <ul className="repo-list">
            {questions.map((question, idx) => (
              <li key={idx}>{question}</li>
            ))}
          </ul>
        </div>
      )}
      <form onSubmit={handleSubmit}>
        <div className="field-block">
          <label className="field-label">Resolution JSON</label>
          <textarea
            className="field-input field-textarea"
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            required
            rows={6}
            placeholder='{"answer": "yes", "details": "..."}'
          />
          <p className="helper-text">Enter the resolution as a valid JSON object.</p>
        </div>
        {error && <div className="error-callout small-callout">{error}</div>}
        <button
          type="submit"
          className="primary-button"
          disabled={loading}
        >
          {loading ? 'Resolving...' : 'Submit Resolution'}
        </button>
      </form>
    </section>
  );
}

function ArtifactsViewer({ task }: { task: TaskRecord }) {
  const [files, setFiles] = useState<RunFile[]>([]);
  const [summary, setSummary] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadArtifacts = async () => {
      if (!task.artifacts_dir) {
        setLoading(false);
        return;
      }

      try {
        const runId = task.artifacts_dir.split('/').pop() || task.artifacts_dir;
        const fileList = await fetchRunFiles(runId);
        setFiles(fileList);

        // Try to load summary.md
        const summaryFile = fileList.find(f => f.path === 'summary.md');
        if (summaryFile) {
          const summaryContent = await fetchRunFile(runId, 'summary.md');
          setSummary(summaryContent);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load artifacts');
      } finally {
        setLoading(false);
      }
    };

    loadArtifacts();
  }, [task.artifacts_dir]);

  if (!task.artifacts_dir) {
    return null;
  }

  if (loading) {
    return <div className="panel callout">Loading artifacts...</div>;
  }

  if (error) {
    return <div className="error-callout">{error}</div>;
  }

  const runId = task.artifacts_dir.split('/').pop() || task.artifacts_dir;
  const repoPlanFiles = files.filter(f => f.path.startsWith('repo-plans/') && f.path.endsWith('plan.md'));
  const promptFiles = files.filter(f => f.path.startsWith('repo-plans/') && f.path.endsWith('agent-prompt.txt'));
  const commandFiles = files.filter(f => f.path.startsWith('repo-plans/') && f.path.endsWith('commands.sh'));

  return (
    <section className="panel">
      <h2 className="section-title">Latest Run Artifacts</h2>
      <p className="section-subtitle">Run ID: {runId}</p>
      
      {summary && (
        <div className="artifact-block">
          <h3 className="artifact-title">Summary</h3>
          <pre className="artifact-preview">{summary}</pre>
        </div>
      )}

      {repoPlanFiles.length > 0 && (
        <div className="artifact-block">
          <h3 className="artifact-title">Repository Plans</h3>
          <ul className="artifact-list">
            {repoPlanFiles.map(file => (
              <li key={file.path}>
                <a
                  href={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'}/api/runs/${runId}/files/${file.path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="artifact-link"
                >
                  {file.path}
                </a>
                <span className="artifact-meta">{Math.round(file.size / 1024)} KB</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {promptFiles.length > 0 && (
        <div className="artifact-block">
          <h3 className="artifact-title">Prompts</h3>
          <ul className="artifact-list">
            {promptFiles.map(file => (
              <li key={file.path}>
                <a
                  href={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'}/api/runs/${runId}/files/${file.path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="artifact-link"
                >
                  {file.path}
                </a>
                <span className="artifact-meta">{Math.round(file.size / 1024)} KB</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {commandFiles.length > 0 && (
        <div className="artifact-block">
          <h3 className="artifact-title">Commands</h3>
          <ul className="artifact-list">
            {commandFiles.map(file => (
              <li key={file.path}>
                <a
                  href={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'}/api/runs/${runId}/files/${file.path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="artifact-link"
                >
                  {file.path}
                </a>
                <span className="artifact-meta">{Math.round(file.size / 1024)} KB</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

export default function TaskDetailPage() {
  const params = useParams();
  const taskId = params.id as string;
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [cancelling, setCancelling] = useState(false);

  const loadTask = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchTask(taskId);
      setTask(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load task');
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  const handleCancel = useCallback(async () => {
    if (!confirm('Are you sure you want to cancel this task?')) {
      return;
    }

    setCancelling(true);
    try {
      await cancelTask(taskId);
      loadTask();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel task');
    } finally {
      setCancelling(false);
    }
  }, [loadTask, taskId]);

  useEffect(() => {
    loadTask();
  }, [loadTask]);

  const canCancel = useMemo(() => {
    if (!task) {
      return false;
    }
    return task.status !== 'SUCCEEDED' && task.status !== 'FAILED' && task.status !== 'CANCELLED';
  }, [task]);

  if (loading) {
    return <div className="panel callout">Loading task...</div>;
  }

  if (error || !task) {
    return (
      <div className="error-callout">{error || 'Task not found'}</div>
    );
  }

  return (
    <div className="page-stack">
      <section className="panel panel-hero">
        <div>
          <Link href="/tasks" className="task-link back-link">
            ← Back to Tasks
          </Link>
          <h1 className="page-title">Task Details</h1>
          <p className="page-subtitle">Inspect lifecycle, request payload, and run artifacts.</p>
        </div>
        {canCancel && (
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="danger-button"
          >
            {cancelling ? 'Cancelling...' : 'Cancel Task'}
          </button>
        )}
      </section>

      <section className="panel">
        <h2 className="section-title">Execution Snapshot</h2>
        <dl className="details-grid">
          <dt>ID</dt>
          <dd>{task.id}</dd>

          <dt>Status</dt>
          <dd>
            <StatusBadge status={task.status} />
          </dd>

          <dt>Created</dt>
          <dd>{new Date(task.created_at).toLocaleString()}</dd>

          <dt>Updated</dt>
          <dd>{new Date(task.updated_at).toLocaleString()}</dd>

          <dt>Attempts</dt>
          <dd>{task.attempts}</dd>

          {task.status_reason && (
            <>
              <dt>Status Reason</dt>
              <dd>{task.status_reason}</dd>
            </>
          )}

          {task.last_error && (
            <>
              <dt>Last Error</dt>
              <dd className="error-text">{task.last_error}</dd>
            </>
          )}

          {task.artifacts_dir && (
            <>
              <dt>Artifacts</dt>
              <dd>{task.artifacts_dir}</dd>
            </>
          )}
        </dl>
      </section>

      <section className="panel">
        <h2 className="section-title">Request Payload</h2>
        <dl className="details-grid">
          <dt>Goal</dt>
          <dd>{task.request.goal}</dd>

          <dt>Repositories</dt>
          <dd>
            <ul className="repo-list">
              {task.request.repos.map((repo, i) => (
                <li key={i}>{repo}</li>
              ))}
            </ul>
          </dd>

          <dt>Max Rounds</dt>
          <dd>{task.request.max_rounds}</dd>

          {task.request.agent_provider && (
            <>
              <dt>Agent Provider</dt>
              <dd>{task.request.agent_provider}</dd>
            </>
          )}
        </dl>
      </section>

      {task.status === 'HITL_REQUIRED' && (
        <HITLResolutionForm task={task} onResolved={loadTask} />
      )}

      <ArtifactsViewer task={task} />
    </div>
  );
}
