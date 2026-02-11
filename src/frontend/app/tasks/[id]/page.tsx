'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { fetchTask, resolveTask, cancelTask, fetchRunFiles, fetchRunFile, TaskRecord, RunFile } from '@/lib/api';

function StatusBadge({ status }: { status: string }) {
  const className = `badge badge-${status.toLowerCase()}`;
  return <span className={className}>{status}</span>;
}

function HITLResolutionForm({ task, onResolved }: { task: TaskRecord; onResolved: () => void }) {
  const [resolution, setResolution] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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
    <div className="bg-white shadow rounded-lg p-6 mb-4">
      <h2 className="text-xl font-bold mb-4">Resolve HITL Task</h2>
      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label className="block text-sm font-bold mb-2">Resolution JSON</label>
          <textarea
            className="w-full border rounded px-3 py-2"
            value={resolution}
            onChange={e => setResolution(e.target.value)}
            required
            rows={6}
            placeholder='{"answer": "yes", "details": "..."}'
          />
          <p className="text-sm text-gray-600 mt-1">
            Enter the resolution as a JSON object
          </p>
        </div>
        {error && (
          <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}
        <button
          type="submit"
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          disabled={loading}
        >
          {loading ? 'Resolving...' : 'Submit Resolution'}
        </button>
      </form>
    </div>
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
    return <div className="text-gray-600">Loading artifacts...</div>;
  }

  if (error) {
    return <div className="p-4 bg-red-100 text-red-700 rounded">{error}</div>;
  }

  const runId = task.artifacts_dir.split('/').pop() || task.artifacts_dir;
  const repoPlanFiles = files.filter(f => f.path.startsWith('repo-plans/') && f.path.endsWith('plan.md'));
  const promptFiles = files.filter(f => f.path.startsWith('prompts/') && f.path.endsWith('copilot-prompt.txt'));
  const commandFiles = files.filter(f => f.path.startsWith('commands/') && f.path.endsWith('commands.sh'));

  return (
    <div className="bg-white shadow rounded-lg p-6 mb-4">
      <h2 className="text-xl font-bold mb-4">Latest Run Artifacts</h2>
      
      {summary && (
        <div className="mb-4">
          <h3 className="font-bold mb-2">Summary</h3>
          <pre className="text-sm">{summary}</pre>
        </div>
      )}

      {repoPlanFiles.length > 0 && (
        <div className="mb-4">
          <h3 className="font-bold mb-2">Repository Plans</h3>
          <ul className="list-disc list-inside">
            {repoPlanFiles.map(file => (
              <li key={file.path}>
                <a
                  href={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'}/api/runs/${runId}/files/${file.path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#3b82f6' }}
                >
                  {file.path}
                </a>
                {' '}({Math.round(file.size / 1024)} KB)
              </li>
            ))}
          </ul>
        </div>
      )}

      {promptFiles.length > 0 && (
        <div className="mb-4">
          <h3 className="font-bold mb-2">Prompts</h3>
          <ul className="list-disc list-inside">
            {promptFiles.map(file => (
              <li key={file.path}>
                <a
                  href={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'}/api/runs/${runId}/files/${file.path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#3b82f6' }}
                >
                  {file.path}
                </a>
                {' '}({Math.round(file.size / 1024)} KB)
              </li>
            ))}
          </ul>
        </div>
      )}

      {commandFiles.length > 0 && (
        <div className="mb-4">
          <h3 className="font-bold mb-2">Commands</h3>
          <ul className="list-disc list-inside">
            {commandFiles.map(file => (
              <li key={file.path}>
                <a
                  href={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'}/api/runs/${runId}/files/${file.path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#3b82f6' }}
                >
                  {file.path}
                </a>
                {' '}({Math.round(file.size / 1024)} KB)
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function TaskDetailPage() {
  const params = useParams();
  const taskId = params.id as string;
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [cancelling, setCancelling] = useState(false);

  const loadTask = async () => {
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
  };

  const handleCancel = async () => {
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
  };

  useEffect(() => {
    loadTask();
  }, [taskId]);

  if (loading) {
    return <div className="text-gray-600">Loading task...</div>;
  }

  if (error || !task) {
    return (
      <div className="p-4 bg-red-100 text-red-700 rounded">
        {error || 'Task not found'}
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div>
          <Link href="/tasks" style={{ color: '#3b82f6', fontSize: '0.875rem' }}>
            ← Back to Tasks
          </Link>
          <h1 className="text-2xl font-bold mt-2">Task Details</h1>
        </div>
        {task.status !== 'SUCCEEDED' && task.status !== 'FAILED' && task.status !== 'CANCELLED' && (
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            {cancelling ? 'Cancelling...' : 'Cancel Task'}
          </button>
        )}
      </div>

      <div className="bg-white shadow rounded-lg p-6 mb-4">
        <div className="grid" style={{ gridTemplateColumns: '200px 1fr', gap: '1rem' }}>
          <div className="font-bold">ID:</div>
          <div>{task.id}</div>

          <div className="font-bold">Status:</div>
          <div><StatusBadge status={task.status} /></div>

          <div className="font-bold">Created:</div>
          <div>{new Date(task.created_at).toLocaleString()}</div>

          <div className="font-bold">Updated:</div>
          <div>{new Date(task.updated_at).toLocaleString()}</div>

          <div className="font-bold">Attempts:</div>
          <div>{task.attempts}</div>

          {task.status_reason && (
            <>
              <div className="font-bold">Status Reason:</div>
              <div>{task.status_reason}</div>
            </>
          )}

          {task.last_error && (
            <>
              <div className="font-bold">Last Error:</div>
              <div className="text-red-700">{task.last_error}</div>
            </>
          )}

          {task.artifacts_dir && (
            <>
              <div className="font-bold">Artifacts:</div>
              <div>{task.artifacts_dir}</div>
            </>
          )}
        </div>
      </div>

      <div className="bg-white shadow rounded-lg p-6 mb-4">
        <h2 className="text-xl font-bold mb-4">Request</h2>
        <div className="grid" style={{ gridTemplateColumns: '200px 1fr', gap: '1rem' }}>
          <div className="font-bold">Goal:</div>
          <div>{task.request.goal}</div>

          <div className="font-bold">Repositories:</div>
          <div>
            <ul className="list-disc list-inside">
              {task.request.repos.map((repo, i) => (
                <li key={i}>{repo}</li>
              ))}
            </ul>
          </div>

          <div className="font-bold">Max Rounds:</div>
          <div>{task.request.max_rounds}</div>

          {task.request.agent_provider && (
            <>
              <div className="font-bold">Agent Provider:</div>
              <div>{task.request.agent_provider}</div>
            </>
          )}
        </div>
      </div>

      {task.status === 'HITL_REQUIRED' && (
        <HITLResolutionForm task={task} onResolved={loadTask} />
      )}

      <ArtifactsViewer task={task} />
    </div>
  );
}
