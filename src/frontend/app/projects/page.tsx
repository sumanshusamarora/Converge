'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createProject,
  fetchDefaultProject,
  fetchProjects,
  ProjectPreferences,
  ProjectRecord,
} from '@/lib/api';

const DEFAULT_PREFERENCES: ProjectPreferences = {
  planning_strategy: 'extend_existing',
  hitl_trigger_mode: 'blockers_only',
  max_hitl_questions: 2,
  execution_flow: 'plan_then_execute',
  allow_custom_instructions_after_plan: true,
  enforce_existing_patterns: true,
  prefer_minimal_changes: true,
  require_best_practice_alignment: false,
  prompt_preamble: null,
};

function ProjectCreateForm({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [defaultRepos, setDefaultRepos] = useState('');
  const [defaultInstructions, setDefaultInstructions] = useState('');
  const [preferences, setPreferences] = useState<ProjectPreferences>(DEFAULT_PREFERENCES);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const updatePreference = useCallback(
    <K extends keyof ProjectPreferences>(key: K, value: ProjectPreferences[K]) => {
      setPreferences((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      await createProject({
        name: name.trim(),
        description: description.trim() || undefined,
        default_repos: defaultRepos
          .split('\n')
          .map((repo) => repo.trim())
          .filter((repo) => repo.length > 0),
        default_instructions: defaultInstructions.trim() || undefined,
        preferences,
      });
      await onCreated();
      onClose();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Create project">
      <div className="modal-panel">
        <div className="modal-head">
          <h2 className="section-title">Create Project</h2>
          <p className="section-subtitle">
            Define defaults once. Tasks under this project will inherit these planning policies.
          </p>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="field-block">
            <label className="field-label">Project Name</label>
            <input
              className="field-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Example: Frontend Experience"
              required
            />
          </div>
          <div className="field-block">
            <label className="field-label">Description</label>
            <textarea
              className="field-input field-textarea"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What this project is responsible for."
            />
          </div>
          <div className="field-block">
            <label className="field-label">Default Repositories (one per line)</label>
            <textarea
              className="field-input field-textarea"
              rows={3}
              value={defaultRepos}
              onChange={(e) => setDefaultRepos(e.target.value)}
              placeholder="src/converge&#10;src/frontend"
            />
          </div>
          <div className="field-block">
            <label className="field-label">Default Instructions</label>
            <textarea
              className="field-input field-textarea"
              rows={3}
              value={defaultInstructions}
              onChange={(e) => setDefaultInstructions(e.target.value)}
              placeholder="Stable guidance applied to every task in this project."
            />
          </div>

          <div className="form-grid">
            <div>
              <label className="field-label">Planning Strategy</label>
              <select
                className="field-input"
                value={preferences.planning_strategy}
                onChange={(e) =>
                  updatePreference(
                    'planning_strategy',
                    e.target.value as ProjectPreferences['planning_strategy'],
                  )
                }
              >
                <option value="extend_existing">Extend existing implementation</option>
                <option value="best_practice_first">Best practice first</option>
              </select>
            </div>
            <div>
              <label className="field-label">HITL Trigger</label>
              <select
                className="field-input"
                value={preferences.hitl_trigger_mode}
                onChange={(e) =>
                  updatePreference(
                    'hitl_trigger_mode',
                    e.target.value as ProjectPreferences['hitl_trigger_mode'],
                  )
                }
              >
                <option value="blockers_only">Blockers only</option>
                <option value="strict">Strict escalation</option>
              </select>
            </div>
            <div>
              <label className="field-label">Max HITL Questions</label>
              <input
                type="number"
                className="field-input"
                min={0}
                max={10}
                value={preferences.max_hitl_questions}
                onChange={(e) => updatePreference('max_hitl_questions', Number(e.target.value))}
              />
            </div>
            <div>
              <label className="field-label">Execution Flow</label>
              <select
                className="field-input"
                value={preferences.execution_flow}
                onChange={(e) =>
                  updatePreference(
                    'execution_flow',
                    e.target.value as ProjectPreferences['execution_flow'],
                  )
                }
              >
                <option value="plan_then_execute">Plan then execute (recommended)</option>
                <option value="plan_and_execute">Allow plan+execute same command</option>
              </select>
            </div>
          </div>

          <div className="choice-list">
            <label className="choice-item">
              <input
                type="checkbox"
                checked={preferences.allow_custom_instructions_after_plan}
                onChange={(e) =>
                  updatePreference('allow_custom_instructions_after_plan', e.target.checked)
                }
              />
              <span>Allow post-plan follow-up instructions</span>
            </label>
            <label className="choice-item">
              <input
                type="checkbox"
                checked={preferences.enforce_existing_patterns}
                onChange={(e) => updatePreference('enforce_existing_patterns', e.target.checked)}
              />
              <span>Enforce existing repo patterns</span>
            </label>
            <label className="choice-item">
              <input
                type="checkbox"
                checked={preferences.prefer_minimal_changes}
                onChange={(e) => updatePreference('prefer_minimal_changes', e.target.checked)}
              />
              <span>Prefer minimal code changes</span>
            </label>
            <label className="choice-item">
              <input
                type="checkbox"
                checked={preferences.require_best_practice_alignment}
                onChange={(e) =>
                  updatePreference('require_best_practice_alignment', e.target.checked)
                }
              />
              <span>Escalate when best-practice alignment is not clear</span>
            </label>
          </div>

          {error && <div className="error-callout small-callout">{error}</div>}

          <div className="modal-actions">
            <button type="button" className="secondary-button" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="primary-button" disabled={loading}>
              {loading ? 'Creating...' : 'Create Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PreferenceChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="pref-chip">
      <strong>{label}:</strong> {value}
    </span>
  );
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [defaultProjectId, setDefaultProjectId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [projectItems, defaultProject] = await Promise.all([
        fetchProjects(),
        fetchDefaultProject(),
      ]);
      setProjects(projectItems);
      setDefaultProjectId(defaultProject.id);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  const summary = useMemo(
    () => ({
      count: projects.length,
      blockersOnly: projects.filter((p) => p.preferences.hitl_trigger_mode === 'blockers_only').length,
      strict: projects.filter((p) => p.preferences.hitl_trigger_mode === 'strict').length,
    }),
    [projects],
  );

  return (
    <div className="page-stack">
      <section className="panel panel-hero">
        <div>
          <p className="eyebrow">Project-first Workflow</p>
          <h1 className="page-title">Projects</h1>
          <p className="page-subtitle">
            Create project defaults first, then create tasks under that project for consistent planning
            and HITL behavior.
          </p>
        </div>
        <div className="hero-actions">
          <Link href="/tasks" className="secondary-button">
            View Tasks
          </Link>
          <button type="button" className="primary-button" onClick={() => setShowCreate(true)}>
            New Project
          </button>
        </div>
      </section>

      <section className="stats-grid stagger-list">
        <article className="metric-card">
          <span>Projects</span>
          <strong>{summary.count}</strong>
        </article>
        <article className="metric-card">
          <span>Blockers-only HITL</span>
          <strong>{summary.blockersOnly}</strong>
        </article>
        <article className="metric-card">
          <span>Strict HITL</span>
          <strong>{summary.strict}</strong>
        </article>
        <article className="metric-card">
          <span>Default Project</span>
          <strong>{defaultProjectId ? defaultProjectId.slice(0, 8) : '—'}</strong>
        </article>
      </section>

      {error && <div className="error-callout">{error}</div>}

      {loading ? (
        <div className="panel callout">Loading projects...</div>
      ) : projects.length === 0 ? (
        <div className="panel callout">No projects yet. Create one to get started.</div>
      ) : (
        <section className="project-grid">
          {projects.map((project) => (
            <article className="panel project-card" key={project.id}>
              <header className="project-card-head">
                <div>
                  <h2 className="section-title">{project.name}</h2>
                  <p className="helper-text">
                    {project.id === defaultProjectId ? 'Default project' : `ID: ${project.id.slice(0, 8)}...`}
                  </p>
                </div>
                <Link href={`/tasks?projectId=${project.id}`} className="primary-button">
                  Open Tasks
                </Link>
              </header>

              <p className="project-description">{project.description || 'No description set.'}</p>

              <div className="pref-row">
                <PreferenceChip label="Planning" value={project.preferences.planning_strategy} />
                <PreferenceChip label="HITL" value={project.preferences.hitl_trigger_mode} />
                <PreferenceChip label="Max HITL" value={String(project.preferences.max_hitl_questions)} />
                <PreferenceChip label="Execution" value={project.preferences.execution_flow} />
              </div>

              <div className="project-meta">
                <p className="helper-text">
                  <strong>Default repos:</strong>{' '}
                  {project.default_repos.length > 0 ? project.default_repos.join(', ') : 'none'}
                </p>
                <p className="helper-text">
                  <strong>Default instructions:</strong>{' '}
                  {project.default_instructions ? 'configured' : 'none'}
                </p>
              </div>
            </article>
          ))}
        </section>
      )}

      {showCreate && <ProjectCreateForm onClose={() => setShowCreate(false)} onCreated={loadProjects} />}
    </div>
  );
}
