"""Codex CLI agent adapter for Converge."""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from converge.agents.base import AgentProvider, AgentResult, AgentTask, CodingAgent
from converge.agents.policy import ExecutionMode

logger = logging.getLogger(__name__)

_DEFAULT_CODEX_MODEL_CANDIDATES = ["gpt-5.3-codex", "gpt-5", "gpt-5-mini"]
_PLAN_MODE_AUTO = "auto"
_PLAN_MODE_FORCE = "force"
_PLAN_MODE_DISABLE = "disable"
_VALID_PLAN_MODES = {_PLAN_MODE_AUTO, _PLAN_MODE_FORCE, _PLAN_MODE_DISABLE}


class CodexAgent(CodingAgent):
    """Codex-based planning agent.

    By default, CodexAgent produces planning prompts and heuristic
    proposals without executing Codex CLI. Set
    CONVERGE_CODING_AGENT_EXEC_ENABLED=true to enable execution gating.
    """

    def __init__(self) -> None:
        """Initialize CodexAgent."""
        self._codex_enabled = (
            os.getenv("CONVERGE_CODING_AGENT_EXEC_ENABLED", "false").lower() == "true"
        )
        self._codex_path = os.getenv("CONVERGE_CODING_AGENT_PATH", "codex")
        self._configured_codex_model = (
            os.getenv("CONVERGE_CODING_AGENT_MODEL", "").strip() or None
        )
        self._resolved_codex_model: str | None = self._configured_codex_model
        self._unavailable_codex_models: set[str] = set()
        logger.info("CodexAgent initialized (codex_enabled=%s)", self._codex_enabled)

    @property
    def provider(self) -> AgentProvider:
        """Return CODEX provider identifier."""
        return AgentProvider.CODEX

    def supports_execution(self) -> bool:
        """Return True (Codex can execute tools when enabled)."""
        return True

    def execute(self, task: AgentTask) -> AgentResult:
        """Execute changes for the given task.

        This method enforces the execution policy and performs safety checks:
        - Verify policy allows execution
        - Check repository exists and has .git directory
        - If create_branch: create new branch with prefix
        - If require_git_clean: ensure working directory is clean
        - Only execute allowlisted commands

        Args:
            task: The task to execute

        Returns:
            AgentResult with execution outcome
        """
        # Check if we have an execution policy
        if task.execution_policy is None:
            return AgentResult(
                provider=self.provider,
                status="FAILED",
                summary="No execution policy provided",
                proposed_changes=[],
                questions_for_hitl=["Task requires execution_policy to execute"],
                raw={"error": "no_execution_policy"},
            )

        policy = task.execution_policy

        # Check if execution is allowed by policy
        if policy.mode != ExecutionMode.EXECUTE_ALLOWED:
            return AgentResult(
                provider=self.provider,
                status="HITL_REQUIRED",
                summary="Execution not allowed by policy",
                proposed_changes=[],
                questions_for_hitl=[
                    f"Execution policy mode is {policy.mode.value}",
                    (
                        "To enable execution: set CONVERGE_CODING_AGENT_EXEC_ENABLED=true "
                        "and --allow-exec flag"
                    ),
                ],
                raw={"policy_mode": policy.mode.value},
            )

        # Perform repository safety checks
        repo_path = Path(task.repo.path)
        if not repo_path.exists():
            return AgentResult(
                provider=self.provider,
                status="FAILED",
                summary=f"Repository path does not exist: {repo_path}",
                proposed_changes=[],
                questions_for_hitl=[f"Repository not found at {repo_path}"],
                raw={"error": "repo_not_found", "path": str(repo_path)},
            )

        git_dir = repo_path / ".git"
        if not git_dir.exists():
            return AgentResult(
                provider=self.provider,
                status="FAILED",
                summary=f"Not a git repository: {repo_path}",
                proposed_changes=[],
                questions_for_hitl=[f"No .git directory found at {repo_path}"],
                raw={"error": "not_git_repo", "path": str(repo_path)},
            )

        # Check if working directory is clean (if required)
        if policy.require_git_clean:
            clean_check = self._check_git_clean(repo_path)
            if not clean_check["clean"]:
                return AgentResult(
                    provider=self.provider,
                    status="FAILED",
                    summary="Working directory is not clean",
                    proposed_changes=[],
                    questions_for_hitl=[
                        "Policy requires clean git working directory",
                        f"Uncommitted changes: {clean_check.get('details', 'unknown')}",
                    ],
                    raw={"error": "git_not_clean", "details": clean_check},
                )

        # Create new branch if requested
        branch_created = None
        if policy.create_branch:
            branch_result = self._create_branch(repo_path, policy.branch_prefix)
            if not branch_result["success"]:
                return AgentResult(
                    provider=self.provider,
                    status="FAILED",
                    summary="Failed to create branch",
                    proposed_changes=[],
                    questions_for_hitl=[
                        f"Could not create branch: {branch_result.get('error', 'unknown')}"
                    ],
                    raw={"error": "branch_creation_failed", "details": branch_result},
                )
            branch_created = branch_result["branch_name"]
            logger.info("Created branch: %s", branch_created)

        # At this point, we would execute Codex CLI or run commands
        # For now, return a placeholder indicating execution is not yet implemented
        logger.warning("Codex CLI execution not yet fully implemented")

        return AgentResult(
            provider=self.provider,
            status="HITL_REQUIRED",
            summary="Execution passed safety checks but Codex CLI not yet implemented",
            proposed_changes=[
                "Safety checks passed",
                f"Repository verified at {repo_path}",
                f"Branch created: {branch_created}" if branch_created else "No branch created",
            ],
            questions_for_hitl=[
                "Codex CLI execution interface not yet implemented",
                "Future iterations will invoke Codex CLI with tool use",
            ],
            raw={
                "safety_checks_passed": True,
                "repo_path": str(repo_path),
                "branch_created": branch_created,
                "policy": {
                    "mode": policy.mode.value,
                    "create_branch": policy.create_branch,
                    "require_git_clean": policy.require_git_clean,
                },
            },
        )

    def _check_git_clean(self, repo_path: Path) -> dict[str, object]:
        """Check if git working directory is clean.

        Args:
            repo_path: Path to repository

        Returns:
            Dict with 'clean' boolean and optional 'details'
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            output = result.stdout.strip()
            return {
                "clean": len(output) == 0,
                "details": output if output else None,
            }
        except subprocess.CalledProcessError as e:
            logger.error("Failed to check git status: %s", e)
            return {"clean": False, "details": f"Error: {e}"}

    def _create_branch(self, repo_path: Path, branch_prefix: str) -> dict[str, object]:
        """Create a new git branch with timestamp.

        Args:
            repo_path: Path to repository
            branch_prefix: Prefix for branch name

        Returns:
            Dict with 'success' boolean, 'branch_name', and optional 'error'
        """
        try:
            # Generate branch name with timestamp
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            branch_name = f"{branch_prefix}{timestamp}"

            # Create and checkout new branch
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            return {"success": True, "branch_name": branch_name}
        except subprocess.CalledProcessError as e:
            logger.error("Failed to create branch: %s", e)
            return {
                "success": False,
                "error": str(e),
                "stderr": e.stderr if hasattr(e, "stderr") else None,
            }

    def plan(self, task: AgentTask) -> AgentResult:
        """Generate a plan using Codex prompt or heuristic.

        Uses Codex CLI first when available/configured, then falls back
        to local heuristic planning if Codex planning cannot run.

        Args:
            task: The planning task with goal, repo, and instructions

        Returns:
            AgentResult with status, summary, and proposed changes
        """
        prompt = self._build_codex_prompt(task)
        prompt_metadata = {
            "prompt_length": len(prompt),
            "repo_path": str(task.repo.path),
            "repo_kind": task.repo.kind,
            "signals": task.repo.signals,
        }

        logger.info(
            "codex_plan_built: prompt_length=%d, repo=%s",
            prompt_metadata["prompt_length"],
            task.repo.path,
        )

        codex_result = self._plan_with_codex_cli(task, prompt, prompt_metadata)
        if codex_result is not None:
            return codex_result

        return self._heuristic_plan(task, prompt, prompt_metadata)

    def plan_diagnostics(self) -> dict[str, object]:
        """Return diagnostics for Codex planning readiness."""
        plan_mode, plan_mode_source = self._codex_plan_mode()

        codex_binary = shutil.which(self._codex_path)
        codex_cli_found = codex_binary is not None
        should_attempt_codex_plan = self._should_attempt_codex_plan(
            codex_cli_found=codex_cli_found,
            plan_mode=plan_mode,
        )

        fallback_reasons = self._plan_fallback_reasons(
            should_attempt_codex_plan=should_attempt_codex_plan,
            plan_mode=plan_mode,
            codex_cli_found=codex_cli_found,
        )
        recommendations = self._plan_recommendations(
            plan_mode=plan_mode,
            codex_cli_found=codex_cli_found,
        )
        model_candidates = self._candidate_codex_models()

        planning_mode: Literal["codex_cli", "heuristic"] = (
            "codex_cli" if should_attempt_codex_plan and codex_cli_found else "heuristic"
        )

        return {
            "codex_path": self._codex_path,
            "codex_binary": codex_binary,
            "codex_cli_found": codex_cli_found,
            "codex_enabled": self._codex_enabled,
            "env": {
                "CONVERGE_CODING_AGENT_EXEC_ENABLED": self._codex_enabled,
                "CONVERGE_CODING_AGENT_PLAN_MODE": plan_mode,
                "CONVERGE_CODING_AGENT_MODEL": self._configured_codex_model,
            },
            "codex_plan_mode": plan_mode,
            "codex_plan_mode_source": plan_mode_source,
            "should_attempt_codex_plan": should_attempt_codex_plan,
            "planning_mode": planning_mode,
            "fallback_reasons": fallback_reasons,
            "recommendations": recommendations,
            "codex_model_configured": self._configured_codex_model,
            "codex_model_selected": self._resolved_codex_model,
            "codex_model_candidates": model_candidates,
            "codex_login_status": self._codex_login_status(codex_binary),
        }

    def _build_codex_prompt(self, task: AgentTask) -> str:
        """Build a structured prompt for Codex CLI.

        Args:
            task: The planning task

        Returns:
            Formatted prompt string
        """
        readme_section = ""
        if task.repo.readme_excerpt:
            readme_section = f"\n## Repository Context\n{task.repo.readme_excerpt}\n"

        signals_section = ""
        if task.repo.signals:
            signals_section = f"\n## Detected Signals\n{', '.join(task.repo.signals)}\n"

        prompt = f"""# Codex Planning Task

## Goal
{task.goal}

## Repository
Path: {task.repo.path}
Kind: {task.repo.kind or "unknown"}
{signals_section}{readme_section}
## Instructions
{task.instructions}

## Task
Analyze the repository and propose a plan to achieve the goal.
List high-level changes needed (no code diffs required).
Identify any risks or questions requiring human judgment.
"""
        return prompt

    def _heuristic_plan(
        self, task: AgentTask, prompt: str, prompt_metadata: dict[str, object]
    ) -> AgentResult:
        """Generate a heuristic plan when Codex execution is disabled.

        Args:
            task: The planning task
            prompt: The built Codex prompt
            prompt_metadata: Metadata about the prompt

        Returns:
            AgentResult with heuristic proposal
        """
        # Heuristic logic based on repo signals
        proposed_changes = []
        questions = []
        is_python_repo = (
            "pyproject.toml" in task.repo.signals
            or "requirements.txt" in task.repo.signals
            or "python_sources" in task.repo.signals
            or task.repo.kind == "python"
        )
        is_node_repo = (
            "package.json" in task.repo.signals
            or "node_sources" in task.repo.signals
            or task.repo.kind == "node"
        )

        if is_python_repo:
            proposed_changes.append("Update Python dependencies if needed for goal")
            proposed_changes.append("Add or modify Python modules to implement feature")
            proposed_changes.append("Update tests for new/modified functionality")
        elif is_node_repo:
            proposed_changes.append("Update Node.js dependencies if needed")
            proposed_changes.append("Add or modify JavaScript/TypeScript modules")
            proposed_changes.append("Update tests for new/modified functionality")
        else:
            proposed_changes.append("Review repository structure and add necessary files")
            # Only mark as question if we truly can't determine type
            if not task.repo.signals:
                questions.append("Repository type unclear; manual analysis required")

        if not Path(task.repo.path).exists():
            questions.append(f"Repository path {task.repo.path} not found; cannot analyze")

        # README missing is informational, not a blocker for heuristic planning
        # (only mark as HITL_REQUIRED if we have real blockers)
        status: Literal["OK", "HITL_REQUIRED", "FAILED"] = "HITL_REQUIRED" if questions else "OK"

        summary = f"Heuristic plan for {task.repo.kind or 'unknown'} repository at {task.repo.path}"

        raw_data: dict[str, object] = {
            "codex_prompt": prompt,
            "prompt_metadata": prompt_metadata,
            "execution_mode": "heuristic",
            "codex_enabled": self._codex_enabled,
            "signals": task.repo.signals,
        }

        return AgentResult(
            provider=self.provider,
            status=status,
            summary=summary,
            proposed_changes=proposed_changes,
            questions_for_hitl=questions,
            raw=raw_data,
        )

    def _plan_with_codex_cli(
        self, task: AgentTask, prompt: str, prompt_metadata: dict[str, object]
    ) -> AgentResult | None:
        codex_binary = shutil.which(self._codex_path)
        plan_mode, _ = self._codex_plan_mode()
        should_attempt_codex_plan = self._should_attempt_codex_plan(
            codex_cli_found=codex_binary is not None,
            plan_mode=plan_mode,
        )

        if not should_attempt_codex_plan:
            return None

        if codex_binary is None:
            logger.info(
                "Codex CLI not found at '%s'; falling back to heuristic plan",
                self._codex_path,
            )
            return None

        if not Path(task.repo.path).exists():
            logger.info("Repo path missing for Codex planning: %s", task.repo.path)
            return None

        model_candidates = self._candidate_codex_models()
        if not model_candidates:
            logger.warning("No Codex model candidates available; falling back to heuristic")
            return None

        with tempfile.TemporaryDirectory(prefix="converge_codex_plan_") as temp_dir:
            temp_dir_path = Path(temp_dir)
            schema_path = temp_dir_path / "plan_schema.json"
            output_path = temp_dir_path / "codex_plan.json"
            schema_path.write_text(json.dumps(self._plan_output_schema()), encoding="utf-8")

            had_model_access_error = False
            for codex_model in model_candidates:
                cmd = [
                    codex_binary,
                    "-a",
                    "never",
                    "exec",
                    "-m",
                    codex_model,
                    "--sandbox",
                    "read-only",
                    "--skip-git-repo-check",
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(output_path),
                    "-C",
                    str(task.repo.path),
                    prompt,
                ]

                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300,
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    logger.warning("Codex planning timed out; falling back to heuristic")
                    return None
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Codex planning invocation failed: %s", exc)
                    return None

                if result.returncode != 0:
                    stderr = (result.stderr or "").strip()
                    stderr_tail = stderr[-1200:] if stderr else "<empty>"
                    if self._is_model_access_error(stderr):
                        had_model_access_error = True
                        self._unavailable_codex_models.add(codex_model)
                        logger.warning(
                            "Codex planning model unavailable (model=%s, exit=%d). stderr_tail=%s",
                            codex_model,
                            result.returncode,
                            stderr_tail,
                        )
                        continue

                    logger.warning(
                        "Codex planning failed (model=%s, exit=%d). stderr_tail=%s",
                        codex_model,
                        result.returncode,
                        stderr_tail,
                    )
                    return None

                if not output_path.exists():
                    logger.warning(
                        "Codex planning produced no output file; falling back to heuristic"
                    )
                    return None

                content = output_path.read_text(encoding="utf-8").strip()
                parsed = self._parse_plan_payload(content)
                if parsed is None:
                    logger.warning("Codex planning output parse failed; falling back to heuristic")
                    return None

                self._resolved_codex_model = codex_model
                summary = parsed.get("summary") or (
                    f"Codex plan for {task.repo.kind or 'repository'} at {task.repo.path}"
                )
                proposed_changes = parsed.get("proposed_changes") or []
                questions_for_hitl = parsed.get("questions_for_hitl") or []

                status: Literal["OK", "HITL_REQUIRED", "FAILED"] = (
                    "HITL_REQUIRED" if questions_for_hitl else "OK"
                )
                raw_data: dict[str, object] = {
                    "codex_prompt": prompt,
                    "prompt_metadata": prompt_metadata,
                    "execution_mode": "codex_cli",
                    "codex_enabled": self._codex_enabled,
                    "signals": task.repo.signals,
                    "codex_stdout": (result.stdout or "")[:2000],
                    "codex_stderr": (result.stderr or "")[:2000],
                    "codex_binary": codex_binary,
                    "codex_model": codex_model,
                    "codex_model_candidates": model_candidates,
                }

                return AgentResult(
                    provider=self.provider,
                    status=status,
                    summary=summary,
                    proposed_changes=proposed_changes,
                    questions_for_hitl=questions_for_hitl,
                    raw=raw_data,
                )

            if had_model_access_error:
                logger.warning(
                    "Codex planning skipped after model access errors. "
                    "Set CONVERGE_CODING_AGENT_MODEL to a model you can access."
                )
            return None

    def _should_attempt_codex_plan(
        self,
        *,
        codex_cli_found: bool | None = None,
        plan_mode: str | None = None,
    ) -> bool:
        mode = plan_mode or self._codex_plan_mode()[0]
        if mode == _PLAN_MODE_DISABLE:
            return False
        if mode == _PLAN_MODE_FORCE:
            return True
        if codex_cli_found is None:
            codex_cli_found = shutil.which(self._codex_path) is not None
        return codex_cli_found

    def _codex_plan_mode(self) -> tuple[str, str]:
        """Resolve codex planning mode and indicate where it came from.

        Returns:
            (mode, source) where mode is one of: auto, force, disable
            and source is one of: configured, default
        """
        configured_mode = os.getenv("CONVERGE_CODING_AGENT_PLAN_MODE", "").strip().lower()
        if configured_mode:
            if configured_mode in _VALID_PLAN_MODES:
                return configured_mode, "configured"
            logger.warning(
                "Invalid CONVERGE_CODING_AGENT_PLAN_MODE=%s; expected auto|force|disable. "
                "Defaulting to auto.",
                configured_mode,
            )
        return _PLAN_MODE_AUTO, "default"

    def _plan_fallback_reasons(
        self,
        *,
        should_attempt_codex_plan: bool,
        plan_mode: str,
        codex_cli_found: bool,
    ) -> list[str]:
        reasons: list[str] = []

        if plan_mode == _PLAN_MODE_DISABLE:
            reasons.append(
                "Coding agent planning disabled by CONVERGE_CODING_AGENT_PLAN_MODE=disable"
            )
        elif not should_attempt_codex_plan:
            reasons.append("Codex planning not enabled for current environment")

        if not codex_cli_found:
            reasons.append(
                f"Codex CLI not found on PATH for CONVERGE_CODING_AGENT_PATH={self._codex_path}"
            )

        return reasons

    def _plan_recommendations(
        self,
        *,
        plan_mode: str,
        codex_cli_found: bool,
    ) -> list[str]:
        recommendations: list[str] = []
        if not codex_cli_found:
            recommendations.append("Install Codex CLI with: converge install-codex-cli --run")
        elif plan_mode == _PLAN_MODE_DISABLE:
            recommendations.append(
                "Set CONVERGE_CODING_AGENT_PLAN_MODE=auto to re-enable Codex planning"
            )
        elif self._configured_codex_model:
            recommendations.append(
                f"Using explicit CONVERGE_CODING_AGENT_MODEL={self._configured_codex_model}. "
                "Remove it to allow automatic model fallback."
            )
        return recommendations

    def _candidate_codex_models(self) -> list[str]:
        if self._configured_codex_model:
            return [self._configured_codex_model]

        candidates_env = os.getenv("CONVERGE_CODING_AGENT_MODEL_CANDIDATES", "").strip()
        if candidates_env:
            base_candidates = [c.strip() for c in candidates_env.split(",") if c.strip()]
        else:
            base_candidates = list(_DEFAULT_CODEX_MODEL_CANDIDATES)

        ordered: list[str] = []
        if self._resolved_codex_model:
            ordered.append(self._resolved_codex_model)
        for candidate in base_candidates:
            if candidate not in ordered and candidate not in self._unavailable_codex_models:
                ordered.append(candidate)
        return ordered

    def _is_model_access_error(self, stderr: str) -> bool:
        lowered = stderr.lower()
        patterns = (
            "does not exist or you do not have access",
            "you do not have access",
            "unknown model",
            "model_not_found",
            "model not found",
            "invalid model",
            "is not supported when using codex",
            "model is not supported",
        )
        return any(pattern in lowered for pattern in patterns)

    def _codex_login_status(self, codex_binary: str | None) -> dict[str, object]:
        if codex_binary is None:
            return {"checked": False, "authenticated": None, "reason": "codex_cli_not_found"}

        try:
            result = subprocess.run(
                [codex_binary, "login", "status"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"checked": True, "authenticated": None, "error": "timeout"}
        except Exception as exc:  # noqa: BLE001
            return {"checked": True, "authenticated": None, "error": str(exc)}

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        combined = f"{stdout}\n{stderr}".lower()

        authenticated: bool | None = None
        if "not logged" in combined or "not authenticated" in combined:
            authenticated = False
        elif result.returncode == 0:
            authenticated = True

        return {
            "checked": True,
            "authenticated": authenticated,
            "exit_code": result.returncode,
            "stdout": stdout[:2000],
            "stderr": stderr[:2000],
        }

    def _parse_plan_payload(self, content: str) -> dict[str, object] | None:
        try:
            payload = json.loads(content)
            if isinstance(payload, dict):
                return self._normalize_plan_payload(payload)
        except json.JSONDecodeError:
            pass

        if "```json" in content:
            start = content.find("```json")
            end = content.find("```", start + len("```json"))
            if start != -1 and end != -1:
                candidate = content[start + len("```json") : end].strip()
                try:
                    payload = json.loads(candidate)
                    if isinstance(payload, dict):
                        return self._normalize_plan_payload(payload)
                except json.JSONDecodeError:
                    return None
        return None

    def _normalize_plan_payload(self, payload: dict[str, object]) -> dict[str, object]:
        summary = str(payload.get("summary", "")).strip()
        proposed_changes = payload.get("proposed_changes", [])
        questions_for_hitl = payload.get("questions_for_hitl", [])

        if not isinstance(proposed_changes, list):
            proposed_changes = [str(proposed_changes)]
        if not isinstance(questions_for_hitl, list):
            questions_for_hitl = [str(questions_for_hitl)]

        return {
            "summary": summary,
            "proposed_changes": [str(change) for change in proposed_changes if str(change).strip()],
            "questions_for_hitl": [
                str(question) for question in questions_for_hitl if str(question).strip()
            ],
        }

    def _plan_output_schema(self) -> dict[str, object]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string"},
                "proposed_changes": {"type": "array", "items": {"type": "string"}},
                "questions_for_hitl": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary", "proposed_changes", "questions_for_hitl"],
        }
