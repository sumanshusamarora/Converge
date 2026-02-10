'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { fetchTasks, createTask, TaskRecord, TaskRequest } from '@/lib/api';

function StatusBadge({ status }: { status: string }) {
  const className = `badge badge-${status.toLowerCase()}`;
  return <span className={className}>{status}</span>;
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
        repos: repos.split('\n').map(r => r.trim()).filter(r => r.length > 0),
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
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
    }}>
      <div className="bg-white rounded-lg p-6 shadow" style={{ width: '600px', maxWidth: '90%' }}>
        <h2 className="text-2xl font-bold mb-4">Create New Task</h2>
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-bold mb-2">Goal</label>
            <textarea
              className="w-full border rounded px-3 py-2"
              value={goal}
              onChange={e => setGoal(e.target.value)}
              required
              rows={3}
              placeholder="Enter task goal..."
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-bold mb-2">Repositories (one per line)</label>
            <textarea
              className="w-full border rounded px-3 py-2"
              value={repos}
              onChange={e => setRepos(e.target.value)}
              required
              rows={4}
              placeholder="repo1&#10;repo2&#10;repo3"
            />
          </div>
          <div className="mb-4 grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <label className="block text-sm font-bold mb-2">Max Rounds</label>
              <input
                type="number"
                className="w-full border rounded px-3 py-2"
                value={maxRounds}
                onChange={e => setMaxRounds(e.target.value)}
                required
                min="1"
              />
            </div>
            <div>
              <label className="block text-sm font-bold mb-2">Agent Provider (optional)</label>
              <select
                className="w-full border rounded px-3 py-2"
                value={agentProvider}
                onChange={e => setAgentProvider(e.target.value)}
              >
                <option value="">Default</option>
                <option value="codex">Codex</option>
                <option value="copilot">Copilot</option>
              </select>
            </div>
          </div>
          {error && (
            <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">
              {error}
            </div>
          )}
          <div className="flex" style={{ gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border rounded"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
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

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);

  const loadTasks = async () => {
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
  };

  useEffect(() => {
    loadTasks();
  }, [statusFilter]);

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Tasks</h1>
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Create Task
        </button>
      </div>

      <div className="mb-4">
        <label className="text-sm font-bold mr-2">Filter by Status:</label>
        <select
          className="border rounded px-3 py-2"
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
        >
          <option value="">All</option>
          <option value="PENDING">PENDING</option>
          <option value="CLAIMED">CLAIMED</option>
          <option value="RUNNING">RUNNING</option>
          <option value="SUCCEEDED">SUCCEEDED</option>
          <option value="FAILED">FAILED</option>
          <option value="HITL_REQUIRED">HITL_REQUIRED</option>
          <option value="CANCELLED">CANCELLED</option>
        </select>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-100 text-red-700 rounded">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-gray-600">Loading tasks...</div>
      ) : tasks.length === 0 ? (
        <div className="text-gray-600">No tasks found.</div>
      ) : (
        <div className="bg-white shadow rounded-lg">
          <table>
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
              {tasks.map(task => (
                <tr key={task.id}>
                  <td>
                    <Link href={`/tasks/${task.id}`} style={{ color: '#3b82f6' }}>
                      {task.id.substring(0, 8)}...
                    </Link>
                  </td>
                  <td>{task.request.goal.substring(0, 60)}{task.request.goal.length > 60 ? '...' : ''}</td>
                  <td><StatusBadge status={task.status} /></td>
                  <td>{task.attempts}</td>
                  <td>{new Date(task.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
