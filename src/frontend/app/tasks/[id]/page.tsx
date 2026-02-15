'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import Timeline from '@/components/Timeline';
import {
  fetchProject,
  TaskRecord,
  TaskEvent,
  HitlPayload,
  HitlQuestion,
  ProjectRecord,
  RunFile,
  createFollowupTask,
  fetchTask,
  fetchTaskEvents,
  resolveTask,
  cancelTask,
  fetchRunFiles,
  fetchRunFile,
  getRunFileUrl,
} from '@/lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080';
const POLL_INTERVAL_MS = 2500;

type LifecycleMetric = {
  label: string;
  value: string;
};

type StepDuration = {
  id: string;
  from: string;
  to: string;
  durationMs: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length > 0);
}

function buildQuestionFromObject(value: Record<string, unknown>, index: number): HitlQuestion | null {
  const idCandidate = value.id ?? value.question_id;
  const id =
    typeof idCandidate === 'string' && idCandidate.trim().length > 0
      ? idCandidate.trim()
      : `q_${index}`;

  const textCandidate = value.text ?? value.question ?? value.prompt ?? value.title;
  const text =
    typeof textCandidate === 'string' && textCandidate.trim().length > 0
      ? textCandidate.trim()
      : '';

  const options = toStringArray(value.options ?? value.choices ?? value.suggested_human_actions);
  const defaultCandidate = value.default ?? value.default_option;
  const defaultValue =
    typeof defaultCandidate === 'string' && defaultCandidate.trim().length > 0
      ? defaultCandidate.trim()
      : undefined;

  if (!text && options.length === 0) {
    return null;
  }

  return {
    id,
    text: text || 'Choose an option',
    options: options.length > 0 ? options : undefined,
    default: defaultValue,
  };
}

function parseHitlPayload(task: TaskRecord): HitlPayload {
  const questions: HitlQuestion[] = [];
  const notes: string[] = [];

  if (task.status_reason) {
    notes.push(task.status_reason);
  }

  (task.hitl_questions || []).forEach((rawQuestion, index) => {
    const trimmed = rawQuestion.trim();
    if (trimmed.length === 0) {
      return;
    }

    let parsed: unknown = trimmed;
    try {
      parsed = JSON.parse(trimmed);
    } catch {
      // keep raw string fallback
    }

    if (typeof parsed === 'string') {
      questions.push({
        id: `q_${index}`,
        text: parsed,
      });
      return;
    }

    if (isRecord(parsed)) {
      const objectQuestion = buildQuestionFromObject(parsed, index);
      if (objectQuestion) {
        questions.push(objectQuestion);
      }

      const nestedQuestions = parsed.questions;
      if (Array.isArray(nestedQuestions)) {
        nestedQuestions.forEach((item, nestedIndex) => {
          if (!isRecord(item)) {
            return;
          }
          const nested = buildQuestionFromObject(item, index * 100 + nestedIndex);
          if (nested) {
            questions.push(nested);
          }
        });
      }

      const notesCandidate = parsed.notes;
      if (typeof notesCandidate === 'string' && notesCandidate.trim().length > 0) {
        notes.push(notesCandidate.trim());
      }
      return;
    }

    questions.push({
      id: `q_${index}`,
      text: trimmed,
    });
  });

  if (questions.length === 0) {
    questions.push({
      id: 'notes',
      text: 'Provide the decision needed to continue this task.',
    });
  }

  return {
    questions,
    notes: notes.length > 0 ? notes.join('\n') : undefined,
  };
}

function runIdFromArtifactsDir(artifactsDir?: string | null): string | null {
  if (!artifactsDir) {
    return null;
  }
  const parts = artifactsDir.split('/').filter((part) => part.length > 0);
  return parts.length > 0 ? parts[parts.length - 1] : null;
}

function parseTimestamp(value: string): number | null {
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return null;
  }
  return parsed;
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms < 0) {
    return '—';
  }
  if (ms < 1000) {
    return `${ms} ms`;
  }
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remSeconds = seconds % 60;
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  if (hours > 0) {
    return `${hours}h ${remMinutes}m ${remSeconds}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${remSeconds}s`;
  }
  return `${seconds}s`;
}

function firstEventTs(events: TaskEvent[], type: TaskEvent['type']): number | null {
  const match = events.find((event) => event.type === type);
  return match ? parseTimestamp(match.ts) : null;
}

function buildLifecycleMetrics(task: TaskRecord, events: TaskEvent[]): LifecycleMetric[] {
  const createdTs = firstEventTs(events, 'TASK_CREATED') ?? parseTimestamp(task.created_at);
  const claimedTs = firstEventTs(events, 'TASK_CLAIMED');
  const executionStartTs = firstEventTs(events, 'EXECUTION_STARTED');
  const hitlRequiredTs = firstEventTs(events, 'HITL_REQUIRED');
  const hitlResolvedTs = firstEventTs(events, 'HITL_RESOLVED');
  const executionEndTs =
    firstEventTs(events, 'EXECUTION_FINISHED') ??
    firstEventTs(events, 'TASK_SUCCEEDED') ??
    firstEventTs(events, 'TASK_FAILED') ??
    parseTimestamp(task.updated_at);

  return [
    {
      label: 'Queue Wait',
      value: formatDuration(
        createdTs !== null && claimedTs !== null ? claimedTs - createdTs : null,
      ),
    },
    {
      label: 'Execution Runtime',
      value: formatDuration(
        executionStartTs !== null && executionEndTs !== null
          ? executionEndTs - executionStartTs
          : null,
      ),
    },
    {
      label: 'HITL Wait',
      value: formatDuration(
        hitlRequiredTs !== null && hitlResolvedTs !== null
          ? hitlResolvedTs - hitlRequiredTs
          : null,
      ),
    },
    {
      label: 'Total Elapsed',
      value: formatDuration(
        createdTs !== null && executionEndTs !== null ? executionEndTs - createdTs : null,
      ),
    },
  ];
}

function buildStepDurations(events: TaskEvent[]): StepDuration[] {
  const result: StepDuration[] = [];
  for (let index = 0; index < events.length - 1; index += 1) {
    const current = events[index];
    const next = events[index + 1];
    const currentTs = parseTimestamp(current.ts);
    const nextTs = parseTimestamp(next.ts);
    if (currentTs === null || nextTs === null || nextTs < currentTs) {
      continue;
    }
    result.push({
      id: `${current.id}-${next.id}`,
      from: current.title,
      to: next.title,
      durationMs: nextTs - currentTs,
    });
  }
  return result;
}

function StatusBadge({ status }: { status: string }) {
  const className = `status-badge status-${status.toLowerCase().replace(/_/g, '-')}`;
  return <span className={className}>{status.replace(/_/g, ' ')}</span>;
}

function HITLResolutionPanel({
  task,
  payload,
  onResolved,
}: {
  task: TaskRecord;
  payload: HitlPayload;
  onResolved: () => Promise<void>;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const runId = runIdFromArtifactsDir(task.artifacts_dir);

  useEffect(() => {
    const initialAnswers: Record<string, string> = {};
    payload.questions.forEach((question) => {
      const defaultValue = question.default || question.options?.[0] || '';
      initialAnswers[question.id] = defaultValue;
    });
    setAnswers(initialAnswers);
  }, [payload]);

  const onAnswerChange = useCallback((questionId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    const missing = payload.questions.find((question) => {
      const answer = answers[question.id];
      return !answer || answer.trim().length === 0;
    });
    if (missing) {
      setError(`Please answer: ${missing.text}`);
      setLoading(false);
      return;
    }

    try {
      const resolution: Record<string, unknown> = {
        answers,
        resolved_at: new Date().toISOString(),
      };
      if (notes.trim().length > 0) {
        resolution.notes = notes.trim();
      }
      await resolveTask(task.id, resolution);
      setSuccess('Resolution submitted. Task was re-queued for processing.');
      await onResolved();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Failed to resolve task');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="section-title">Human Input Required</h2>
      <p className="section-subtitle">
        Answer the questions below to resolve this HITL checkpoint and resume processing.
      </p>
      {payload.notes && <div className="info-callout">{payload.notes}</div>}
      {runId && (
        <p className="helper-text">
          Run artifacts:{' '}
          <a
            className="task-link"
            href={`${API_BASE}/api/runs/${runId}/files`}
            target="_blank"
            rel="noopener noreferrer"
          >
            View run files
          </a>
        </p>
      )}
      <form onSubmit={handleSubmit} className="hitl-form">
        {payload.questions.map((question) => (
          <div className="field-block" key={question.id}>
            <label className="field-label">{question.text}</label>
            {question.options && question.options.length > 0 ? (
              <div className="choice-list">
                {question.options.map((option) => (
                  <label className="choice-item" key={`${question.id}-${option}`}>
                    <input
                      type="radio"
                      name={question.id}
                      value={option}
                      checked={(answers[question.id] || '') === option}
                      onChange={(e) => onAnswerChange(question.id, e.target.value)}
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            ) : (
              <input
                type="text"
                className="field-input"
                value={answers[question.id] || ''}
                onChange={(e) => onAnswerChange(question.id, e.target.value)}
                placeholder="Enter answer"
              />
            )}
          </div>
        ))}
        <div className="field-block">
          <label className="field-label">Additional Notes (optional)</label>
          <textarea
            className="field-input field-textarea"
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Provide any context for the worker or reviewers."
          />
        </div>
        {error && <div className="error-callout small-callout">{error}</div>}
        {success && <div className="success-callout small-callout">{success}</div>}
        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? 'Submitting...' : 'Submit Resolution'}
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

  const runId = runIdFromArtifactsDir(task.artifacts_dir);

  useEffect(() => {
    const loadArtifacts = async () => {
      if (!runId) {
        setLoading(false);
        return;
      }

      try {
        const fileList = await fetchRunFiles(runId);
        setFiles(fileList);

        const summaryFile = fileList.find((file) => file.path === 'summary.md');
        if (summaryFile) {
          const summaryContent = await fetchRunFile(runId, summaryFile.path);
          setSummary(summaryContent);
        }
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load artifacts');
      } finally {
        setLoading(false);
      }
    };

    void loadArtifacts();
  }, [runId]);

  if (!runId) {
    return null;
  }

  if (loading) {
    return <div className="panel callout">Loading artifacts...</div>;
  }

  if (error) {
    return <div className="error-callout">{error}</div>;
  }

  const repoPlanFiles = files.filter(
    (file) => file.path.startsWith('repo-plans/') && file.path.endsWith('plan.md'),
  );

  return (
    <section className="panel">
      <h2 className="section-title">Artifacts</h2>
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
            {repoPlanFiles.map((file) => (
              <li key={file.path}>
                <a
                  href={getRunFileUrl(runId, file.path)}
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

function FollowupInstructionPanel({
  task,
  onCreated,
}: {
  task: TaskRecord;
  onCreated: (newTaskId: string) => void;
}) {
  const [instruction, setInstruction] = useState('');
  const [executeImmediately, setExecuteImmediately] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!instruction.trim()) {
      setError('Please provide an instruction for the follow-up run.');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const created = await createFollowupTask(task.id, instruction.trim(), executeImmediately);
      setSuccess(`Follow-up task created: ${created.id}`);
      setInstruction('');
      setExecuteImmediately(false);
      onCreated(created.id);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Failed to create follow-up');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="section-title">Refine Plan</h2>
      <p className="section-subtitle">
        Create a follow-up task with additional instructions after reviewing current plan/artifacts.
      </p>
      <form onSubmit={handleSubmit} className="hitl-form">
        <div className="field-block">
          <label className="field-label">Additional Instruction</label>
          <textarea
            className="field-input field-textarea"
            rows={3}
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="Example: Prioritize incremental API changes and keep UI dependencies minimal."
          />
        </div>
        <label className="choice-item">
          <input
            type="checkbox"
            checked={executeImmediately}
            onChange={(e) => setExecuteImmediately(e.target.checked)}
          />
          <span>Request immediate execution in the same task (project policy may block this)</span>
        </label>
        {error && <div className="error-callout small-callout">{error}</div>}
        {success && <div className="success-callout small-callout">{success}</div>}
        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? 'Creating...' : 'Create Follow-up Task'}
        </button>
      </form>
    </section>
  );
}

export default function TaskDetailPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.id as string;

  const [task, setTask] = useState<TaskRecord | null>(null);
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [error, setError] = useState('');
  const [cancelling, setCancelling] = useState(false);

  const loadTask = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoading(true);
      }
      try {
        const data = await fetchTask(taskId);
        setTask(data);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load task');
      } finally {
        if (!silent) {
          setLoading(false);
        }
      }
    },
    [taskId],
  );

  useEffect(() => {
    if (!task?.project_id) {
      setProject(null);
      return;
    }
    let cancelled = false;
    const loadProject = async () => {
      try {
        const loaded = await fetchProject(task.project_id);
        if (!cancelled) {
          setProject(loaded);
        }
      } catch {
        if (!cancelled) {
          setProject(null);
        }
      }
    };
    void loadProject();
    return () => {
      cancelled = true;
    };
  }, [task?.project_id]);

  const loadEvents = useCallback(
    async (silent = false) => {
      if (!silent) {
        setEventsLoading(true);
      }
      try {
        const data = await fetchTaskEvents(taskId);
        setEvents(data);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load timeline');
      } finally {
        if (!silent) {
          setEventsLoading(false);
        }
      }
    },
    [taskId],
  );

  const refreshTaskAndEvents = useCallback(
    async (silent = false) => {
      await Promise.all([loadTask(silent), loadEvents(silent)]);
    },
    [loadEvents, loadTask],
  );

  useEffect(() => {
    setError('');
    void refreshTaskAndEvents(false);
  }, [refreshTaskAndEvents]);

  useEffect(() => {
    if (!task) {
      return;
    }
    if (task.status !== 'RUNNING' && task.status !== 'CLAIMED') {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshTaskAndEvents(true);
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [refreshTaskAndEvents, task]);

  const handleCancel = useCallback(async () => {
    if (!window.confirm('Are you sure you want to cancel this task?')) {
      return;
    }
    setCancelling(true);
    try {
      await cancelTask(taskId);
      await refreshTaskAndEvents(true);
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : 'Failed to cancel task');
    } finally {
      setCancelling(false);
    }
  }, [refreshTaskAndEvents, taskId]);

  const canCancel = useMemo(() => {
    if (!task) {
      return false;
    }
    return !['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(task.status);
  }, [task]);

  const hitlPayload = useMemo(() => (task ? parseHitlPayload(task) : null), [task]);
  const lifecycleMetrics = useMemo(
    () => (task ? buildLifecycleMetrics(task, events) : []),
    [events, task],
  );
  const stepDurations = useMemo(() => buildStepDurations(events), [events]);
  const runId = runIdFromArtifactsDir(task?.artifacts_dir);

  if (loading) {
    return <div className="panel callout">Loading task...</div>;
  }

  if (error && !task) {
    return <div className="error-callout">{error}</div>;
  }

  if (!task) {
    return <div className="error-callout">Task not found</div>;
  }

  return (
    <div className="page-stack">
      <section className="panel panel-hero">
        <div>
          <Link href="/tasks" className="task-link back-link">
            ← Back to Tasks
          </Link>
          <h1 className="page-title">Task Timeline</h1>
          <p className="page-subtitle">{task.request.goal}</p>
        </div>
        {canCancel && (
          <button onClick={handleCancel} disabled={cancelling} className="danger-button">
            {cancelling ? 'Cancelling...' : 'Cancel Task'}
          </button>
        )}
      </section>

      {error && <div className="error-callout">{error}</div>}

      <section className="panel">
        <h2 className="section-title">Overview</h2>
        <dl className="details-grid">
          <dt>Task ID</dt>
          <dd>{task.id}</dd>

          <dt>Status</dt>
          <dd>
            <StatusBadge status={task.status} />
          </dd>

          <dt>Project</dt>
          <dd>
            <Link href={`/tasks?projectId=${task.project_id}`} className="task-link">
              {project ? project.name : `${task.project_id.slice(0, 8)}...`}
            </Link>
          </dd>

          <dt>Attempts</dt>
          <dd>{task.attempts}</dd>

          <dt>Created</dt>
          <dd>{new Date(task.created_at).toLocaleString()}</dd>

          <dt>Updated</dt>
          <dd>{new Date(task.updated_at).toLocaleString()}</dd>

          <dt>Provider</dt>
          <dd>{task.request.agent_provider || 'default'}</dd>

          <dt>Execution Mode</dt>
          <dd>{String(task.request.metadata?.execution_mode || 'n/a')}</dd>

          <dt>Custom Instructions</dt>
          <dd>{task.request.custom_instructions || 'none'}</dd>

          <dt>Repositories</dt>
          <dd>
            <ul className="repo-list">
              {task.request.repos.map((repo) => (
                <li key={repo}>{repo}</li>
              ))}
            </ul>
          </dd>

          {task.last_error && (
            <>
              <dt>Last Error</dt>
              <dd className="error-text">{task.last_error}</dd>
            </>
          )}

          {runId && (
            <>
              <dt>Run Files</dt>
              <dd>
                <a
                  href={`${API_BASE}/api/runs/${runId}/files`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="task-link"
                >
                  Open run files
                </a>
              </dd>
            </>
          )}
        </dl>
      </section>

      {task.status === 'HITL_REQUIRED' && hitlPayload && (
        <HITLResolutionPanel
          task={task}
          payload={hitlPayload}
          onResolved={() => refreshTaskAndEvents(true)}
        />
      )}

      <section className="panel">
        <h2 className="section-title">Lifecycle Metrics</h2>
        <p className="section-subtitle">Execution timing computed from task timeline events.</p>
        <div className="metrics-inline-grid">
          {lifecycleMetrics.map((metric) => (
            <article className="mini-metric-card" key={metric.label}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </article>
          ))}
        </div>
        {stepDurations.length > 0 && (
          <div className="step-duration-block">
            <h3 className="artifact-title">Step Durations</h3>
            <div className="table-wrap">
              <table className="tasks-table compact-table">
                <thead>
                  <tr>
                    <th>From</th>
                    <th>To</th>
                    <th>Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {stepDurations.map((step) => (
                    <tr key={step.id}>
                      <td>{step.from}</td>
                      <td>{step.to}</td>
                      <td>{formatDuration(step.durationMs)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      <section className="panel">
        <h2 className="section-title">Timeline</h2>
        <p className="section-subtitle">Events for the latest run and task lifecycle.</p>
        <Timeline events={events} loading={eventsLoading} />
      </section>

      {task.status !== 'RUNNING' && task.status !== 'CLAIMED' && (
        <FollowupInstructionPanel
          task={task}
          onCreated={(newTaskId) => {
            router.push(`/tasks/${newTaskId}`);
          }}
        />
      )}

      <ArtifactsViewer task={task} />
    </div>
  );
}
