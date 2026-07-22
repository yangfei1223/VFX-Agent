# Kimi Code Backend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Kimi Code CLI (v0.28.1, K3 model) as the third `BaseBackend` adapter alongside CodexBackend and ClaudeCodeBackend.

**Architecture:** Same shape as ClaudeCodeBackend — subclass `BaseBackend`, override the 3 abstract methods (`setup_workspace` / `build_command` / `parse_event`), auto-register via `register_backend()` on import. CLI invoked via subprocess with `stream-json` output; OpenAI chat completion style events mapped to unified `AgentEvent`.

**Tech Stack:** Python 3.11+, FastAPI backend (existing), Kimi Code CLI v0.28.1 (`~/.kimi-code/bin/kimi`), pytest for unit tests.

**Spec:** `docs/superpowers/specs/2026-07-22-kimi-backend-design.md`

---

## Reference Files (read once before starting)

| File | Purpose |
|------|---------|
| `backend/app/backends/base.py` (185 lines) | BaseBackend ABC + AgentEvent TypedDict + concrete stream() |
| `backend/app/backends/claude_code.py` (178 lines) | Closest sibling backend to model after |
| `backend/app/backends/codex.py` (114 lines) | Alternative sibling for setup_workspace pattern |
| `backend/app/backends/__init__.py` (46 lines) | Registry + auto-import pattern |
| `backend/app/config.py` | Existing env var loading |
| `backend/.env.example` | Existing env var documentation |
| `backend/tests/unit/test_backend_registry.py` | Registry test pattern |
| `backend/tests/unit/test_backends_base.py` | parse_event test pattern |

**Worktree:** `/Users/yangfei/Code/VFX-Agent/.worktrees/v2.0-codex-od/`
**Branch:** `feat/backend-ext`

---

## Task 1: Add KIMI_BIN_PATH env var

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`

**Step 1: Read existing config.py to confirm placement**

Run: `cat backend/app/config.py`
Expected: see existing env var loading pattern (CODEX_MODEL, etc.)

**Step 2: Add KIMI_BIN_PATH to config.py**

Add one line in the appropriate section (near other backend-related env vars, or at end of env-loading block):

```python
# Kimi Code CLI binary path (default: official install location; override with `kimi` if installed via npm -g)
KIMI_BIN_PATH = os.getenv("KIMI_BIN_PATH", os.path.expanduser("~/.kimi-code/bin/kimi"))
```

If config.py uses `Settings` class / pydantic, add as class field with default value matching above.

**Step 3: Add to .env.example**

Append to backend/.env.example:

```env
# Kimi Code CLI binary (default: ~/.kimi-code/bin/kimi; set to `kimi` if installed via npm -g)
# KIMI_BIN_PATH=/Users/yangfei/.kimi-code/bin/kimi
```

**Step 4: Commit**

```bash
git add backend/app/config.py backend/.env.example
git commit -m "feat(backends): add KIMI_BIN_PATH env var

Default resolves to ~/.kimi-code/bin/kimi (official install location
for Kimi Code CLI v0.28.1). Users who installed via npm -g can set
KIMI_BIN_PATH=kimi to use PATH lookup."
```

---

## Task 2: Write failing unit tests for KimiBackend

**Files:**
- Create: `backend/tests/unit/test_kimi_backend.py`

**Step 1: Write the failing test file**

```python
"""Unit tests for KimiBackend.parse_event mapping.

Tests cover all observed Kimi v0.28.1 stream-json event shapes:
- assistant with tool_calls only
- assistant with content only (text)
- assistant with content + tool_calls (mixed; tool_call wins)
- tool result
- meta session.resume_hint (dropped)
- unknown event (fallback to text)
- empty / malformed input (no raise, fallback to text)
"""
import pytest

from app.backends import BACKEND_REGISTRY
from app.backends.base import AgentEvent, BaseBackend
from app.backends.kimi import KimiBackend


class TestKimiBackendRegistration:
    """Registry + class structure sanity checks."""

    def test_registered_in_registry(self):
        """KimiBackend auto-registers on import via register_backend()."""
        assert "kimi" in BACKEND_REGISTRY

    def test_registry_class_is_kimi(self):
        assert BACKEND_REGISTRY["kimi"] is KimiBackend

    def test_is_basebackend_subclass(self):
        assert issubclass(KimiBackend, BaseBackend)

    def test_name_attr(self):
        assert KimiBackend.name == "kimi"


class TestKimiParseEvent:
    """parse_event mapping tests. Each test feeds a raw dict that mirrors
    real kimi stream-json output and asserts the resulting AgentEvent.
    """

    def setup_method(self):
        # parse_event is stateless; instance not strictly required but
        # instantiate to catch __init__ signature regressions.
        self.backend = KimiBackend(proxy=None, timeout_seconds=600)

    def test_assistant_with_tool_calls_becomes_tool_call(self):
        raw = {
            "role": "assistant",
            "tool_calls": [
                {
                    "type": "function",
                    "id": "tool_abc",
                    "function": {
                        "name": "Bash",
                        "arguments": '{"command":"ls"}',
                    },
                }
            ],
        }
        ev = self.backend.parse_event(raw)
        assert ev is not None
        assert ev["type"] == "tool_call"
        assert ev["content"] == "Bash"
        assert ev["usage"] is None
        assert ev["raw"] is raw

    def test_assistant_with_multiple_tool_calls_joins_names(self):
        raw = {
            "role": "assistant",
            "tool_calls": [
                {"type": "function", "id": "t1", "function": {"name": "Read", "arguments": "{}"}},
                {"type": "function", "id": "t2", "function": {"name": "Bash", "arguments": "{}"}},
            ],
        }
        ev = self.backend.parse_event(raw)
        assert ev["type"] == "tool_call"
        # Order preserved; joined by ", "
        assert ev["content"] == "Read, Bash"

    def test_assistant_with_content_only_becomes_text(self):
        raw = {"role": "assistant", "content": "Done. Wrote the file."}
        ev = self.backend.parse_event(raw)
        assert ev["type"] == "text"
        assert ev["content"] == "Done. Wrote the file."

    def test_assistant_with_content_and_tool_calls_prefers_tool_call(self):
        """Mixed: tool_calls wins (matches claude_code behavior)."""
        raw = {
            "role": "assistant",
            "content": "I'll write the file now.",
            "tool_calls": [
                {"type": "function", "id": "x", "function": {"name": "Write", "arguments": "{}"}},
            ],
        }
        ev = self.backend.parse_event(raw)
        assert ev["type"] == "tool_call"
        assert ev["content"] == "Write"

    def test_tool_result_event(self):
        raw = {
            "role": "tool",
            "tool_call_id": "tool_abc",
            "content": "Command executed successfully.",
        }
        ev = self.backend.parse_event(raw)
        assert ev["type"] == "tool_result"
        # content left empty (raw preserved for frontend deep-read)
        assert ev["content"] == ""
        assert ev["raw"] is raw

    def test_meta_session_resume_hint_is_dropped(self):
        """meta/session.resume_hint is session-end noise; parse_event returns None."""
        raw = {
            "role": "meta",
            "type": "session.resume_hint",
            "session_id": "session_abc",
            "command": "kimi -r session_abc",
            "content": "To resume this session: ...",
        }
        ev = self.backend.parse_event(raw)
        assert ev is None

    def test_meta_other_types_fallback_to_text(self):
        """Unknown meta types are not silently dropped; only session.resume_hint is."""
        raw = {"role": "meta", "type": "unknown_future_type", "content": "foo"}
        ev = self.backend.parse_event(raw)
        assert ev is not None
        assert ev["type"] == "text"

    def test_unknown_event_falls_back_to_text(self):
        raw = {"role": "system", "message": "something weird"}
        ev = self.backend.parse_event(raw)
        assert ev is not None
        assert ev["type"] == "text"
        assert ev["content"] == ""
        assert ev["raw"] is raw

    def test_empty_dict_falls_back_to_text(self):
        """parse_event must never raise, even on empty input."""
        ev = self.backend.parse_event({})
        assert ev is not None
        assert ev["type"] == "text"

    def test_missing_role_field_does_not_raise(self):
        raw = {"content": "no role here"}
        ev = self.backend.parse_event(raw)
        assert ev is not None
        assert ev["type"] == "text"


class TestKimiBuildCommand:
    """build_command should produce a valid argv. No subprocess actually runs."""

    def test_command_shape_default_bin(self, monkeypatch, tmp_path):
        # Ensure default path is used when env unset
        monkeypatch.delenv("KIMI_BIN_PATH", raising=False)
        backend = KimiBackend(proxy=None, timeout_seconds=600)
        cmd = backend.build_command(
            workdir=tmp_path,
            prompt="hello world",
            keyframes=["/abs/keyframe.png"],
        )
        assert cmd[0].endswith("kimi")
        assert "-p" in cmd
        assert "hello world" in cmd
        assert "--output-format" in cmd
        assert "stream-json" in cmd
        # keyframes should NOT appear as CLI args (kimi has no -i flag;
        # they go in the prompt body)
        assert "/abs/keyframe.png" not in cmd

    def test_command_uses_env_bin_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("KIMI_BIN_PATH", "/custom/path/kimi")
        backend = KimiBackend(proxy=None, timeout_seconds=600)
        cmd = backend.build_command(tmp_path, "p", [])
        assert cmd[0] == "/custom/path/kimi"


class TestKimiSetupWorkspace:
    """setup_workspace should symlink skills/ + AGENTS.md + CLAUDE.md.
    Pattern is identical to CodexBackend / ClaudeCodeBackend."""

    def test_setup_creates_all_three_symlinks(self, tmp_path):
        # Build a fake skills_src
        skills_src = tmp_path / "skills_src"
        skills_src.mkdir()
        (skills_src / "AGENTS.md").write_text("# fake AGENTS")
        (skills_src / "vfx-shader").mkdir()
        (skills_src / "vfx-shader" / "SKILL.md").write_text("# fake SKILL")

        workdir = tmp_path / "workdir"
        workdir.mkdir()

        backend = KimiBackend(proxy=None, timeout_seconds=600)
        backend.setup_workspace(workdir, skills_src)

        # All 3 symlinks created
        assert (workdir / "skills").is_symlink()
        assert (workdir / "skills").resolve() == skills_src.resolve()
        assert (workdir / "AGENTS.md").is_symlink()
        assert (workdir / "CLAUDE.md").is_symlink()
        # AGENTS.md and CLAUDE.md point to same source
        assert (workdir / "AGENTS.md").resolve() == (skills_src / "AGENTS.md").resolve()
        assert (workdir / "CLAUDE.md").resolve() == (skills_src / "AGENTS.md").resolve()

    def test_setup_is_idempotent(self, tmp_path):
        """Calling setup_workspace twice must not error (symlink exists check)."""
        skills_src = tmp_path / "skills_src"
        skills_src.mkdir()
        (skills_src / "AGENTS.md").write_text("# fake")

        workdir = tmp_path / "workdir"
        workdir.mkdir()

        backend = KimiBackend(proxy=None, timeout_seconds=600)
        backend.setup_workspace(workdir, skills_src)
        # Second call: should be no-op, not raise
        backend.setup_workspace(workdir, skills_src)
        assert (workdir / "AGENTS.md").exists()
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/unit/test_kimi_backend.py -v
```

Expected: All tests FAIL with `ImportError: No module named 'app.backends.kimi'` (module not yet created).

---

## Task 3: Implement KimiBackend

**Files:**
- Create: `backend/app/backends/kimi.py`

**Step 1: Write the implementation**

```python
"""KimiBackend: wraps Moonshot Kimi Code CLI (v0.28.1) for headless execution.

Closest sibling: ClaudeCodeBackend. Same shape (subprocess + stream-json),
same `cwd=` workdir mechanism, same AGENTS.md auto-load behavior, same
prompt-lists-image-paths approach for multimodal input.

Key differences from ClaudeCodeBackend (see spec
docs/superpowers/specs/2026-07-22-kimi-backend-design.md):
- Binary at ~/.kimi-code/bin/kimi (NOT in PATH by default)
- No --yolo / --auto flag needed (kimi -p auto-approves tool calls)
- No --allowedTools flag (no granular allow-listing)
- No -C flag for workdir (uses subprocess cwd=)
- Event schema is OpenAI chat completion style ({role, content/tool_calls})
- No token usage output → all events have usage=None
- No terminal result event → orchestrator detects completion via proc exit code
- Multimodal via k3 native image_in + agent's built-in ReadMediaFile tool
  (no MCP server needed, unlike claude-code which needs zai-mcp-server)

Default model: kimi-code/k3 (K3, 1M context, capabilities: thinking + image_in
+ video_in + tool_use). Configured in ~/.kimi-code/config.toml.
"""
import os
from pathlib import Path
from typing import Optional

from .base import BaseBackend, AgentEvent
from . import register_backend


class KimiBackend(BaseBackend):
    """Adapter for Kimi Code CLI (kimi-code v0.28.1+)."""

    name = "kimi"

    # Events to drop at parse time. Currently only the session-end marker;
    # if kimi emits more noise types in future versions, add them here.
    #
    # Background: kimi emits a final {"role":"meta","type":"session.resume_hint"}
    # event after the agent loop completes. This carries no debugging value
    # (just a "kimi -r <session_id>" hint to resume interactively). Dropping
    # it keeps the events buffer clean.
    DROP_META_TYPES = frozenset({"session.resume_hint"})

    def setup_workspace(self, workdir: Path, skills_src: Path) -> None:
        """Create symlinks for AGENTS.md + CLAUDE.md + skills/ at workdir root.

        Identical pattern to CodexBackend. kimi auto-loads workdir/AGENTS.md
        (verified via v0.28.1 test: AGENTS.md prefix rule applied). CLAUDE.md
        symlink is defensive (AGENTS.md content is already backend-neutral;
        harmless for kimi which does not auto-load CLAUDE.md).
        """
        # Symlink skills/ at workdir root (kimi auto-discovers from cwd)
        skills_link = workdir / "skills"
        if not skills_link.exists():
            skills_link.symlink_to(skills_src.absolute(), target_is_directory=True)

        # Symlink AGENTS.md (kimi primary discovery)
        agents_link = workdir / "AGENTS.md"
        if not agents_link.exists():
            agents_link.symlink_to((skills_src / "AGENTS.md").resolve())

        # Symlink CLAUDE.md -> same source (defensive; harmless for kimi)
        claude_link = workdir / "CLAUDE.md"
        if not claude_link.exists():
            claude_link.symlink_to((skills_src / "AGENTS.md").resolve())

    def build_command(
        self, workdir: Path, prompt: str, keyframes: list[str],
    ) -> list[str]:
        """Build `kimi -p` argv.

        NOTE: workdir is NOT in argv. It's passed via subprocess cwd= parameter
        (handled by BaseBackend.stream()).

        NOTE: keyframes are NOT passed via CLI flag. They are listed in the
        user prompt as absolute paths; the k3 agent uses its built-in
        ReadMediaFile tool to read them (k3 has native image_in capability).

        NOTE: no --yolo / --auto flag. kimi v0.28.1 in -p mode auto-approves
        tool calls (verified via Bash/Write test). Attempting to add --yolo
        with -p raises "Cannot combine --prompt with --yolo".
        """
        bin_path = os.getenv(
            "KIMI_BIN_PATH",
            os.path.expanduser("~/.kimi-code/bin/kimi"),
        )
        return [
            bin_path,
            "-p", prompt,
            "--output-format", "stream-json",
        ]

    def parse_event(self, raw: dict) -> Optional[AgentEvent]:
        """Map Kimi stream-json event to unified AgentEvent.

        Returns None for the session-end meta marker so it is filtered at the
        BaseBackend.stream() layer before reaching orchestrator's events buffer.

        Kimi event schema (OpenAI chat completion style, JSONL):
            {"role":"assistant","tool_calls":[...]}     -> tool_call
            {"role":"assistant","content":"<text>"}     -> text
            {"role":"assistant","content":"...","tool_calls":[...]}
                                                         -> tool_call (mixed wins)
            {"role":"tool","tool_call_id":"...","content":"..."}
                                                         -> tool_result
            {"role":"meta","type":"session.resume_hint"} -> None (drop)
            other / unknown                              -> text fallback

        Token usage: kimi v0.28.1 does not emit token counts in -p mode.
        All returned events have usage=None. Frontend usage panel renders
        "—" for kimi backend.
        """
        role = raw.get("role", "")

        # Drop session-end noise
        if role == "meta":
            meta_type = raw.get("type", "")
            if meta_type in self.DROP_META_TYPES:
                return None
            # Unknown meta types: fall through to text fallback (do not
            # silently swallow future meta events).

        if role == "assistant":
            tool_calls = raw.get("tool_calls") or []
            if tool_calls:
                # tool_call wins even if content present (matches claude_code)
                tool_names = ", ".join(
                    tc.get("function", {}).get("name", "")
                    for tc in tool_calls
                    if isinstance(tc, dict)
                )
                return {
                    "type": "tool_call",
                    "content": tool_names,
                    "usage": None,
                    "raw": raw,
                }
            # No tool_calls: pure text response
            return {
                "type": "text",
                "content": raw.get("content", ""),
                "usage": None,
                "raw": raw,
            }

        if role == "tool":
            return {
                "type": "tool_result",
                "content": "",  # raw preserved; frontend can deep-read tool_call_id
                "usage": None,
                "raw": raw,
            }

        # Unknown / malformed event: text fallback, never raise.
        # Covers: empty dict, missing role field, future event types.
        return {
            "type": "text",
            "content": "",
            "usage": None,
            "raw": raw,
        }


# Auto-register on import (triggers when backends/__init__.py imports this module)
register_backend("kimi", KimiBackend)
```

**Step 2: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/unit/test_kimi_backend.py -v
```

Expected: All 16 tests PASS.

**Step 3: Commit (kimi.py only; __init__.py change is next task)**

```bash
git add backend/app/backends/kimi.py backend/tests/unit/test_kimi_backend.py
git commit -m "feat(backends): add KimiBackend (Kimi Code CLI v0.28.1, K3)

Third BaseBackend adapter alongside CodexBackend / ClaudeCodeBackend.
Same shape (subprocess + stream-json), OpenAI chat completion event
schema mapped to unified AgentEvent.

Key behaviors verified via v0.28.1 manual tests:
- kimi -p auto-approves tool calls (no --yolo/--auto flag needed)
- workdir/AGENTS.md auto-loaded (kimi reads cwd root)
- k3 native image_in + built-in ReadMediaFile tool (no MCP needed)
- meta/session.resume_hint is session-end noise, dropped
- No token usage emitted in -p mode (usage=None for all events)

Includes 16 unit tests covering parse_event all event types,
build_command shape, and setup_workspace symlink creation."
```

---

## Task 4: Register KimiBackend in backends/__init__.py

**Files:**
- Modify: `backend/app/backends/__init__.py:45-46`

**Step 1: Read current state to confirm line numbers**

Run: `cat backend/app/backends/__init__.py`
Expected: see lines 45-46:
```python
from . import codex as _codex  # noqa: F401 (triggers register_backend on import)
from . import claude_code as _claude_code  # noqa: F401 (triggers register_backend)
```

**Step 2: Add kimi import after claude_code**

Change lines 45-46 area to:

```python
from . import codex as _codex  # noqa: F401 (triggers register_backend on import)
from . import claude_code as _claude_code  # noqa: F401 (triggers register_backend)
from . import kimi as _kimi  # noqa: F401 (triggers register_backend)
```

**Step 3: Run all unit tests to verify nothing regressed**

```bash
cd backend && python -m pytest tests/unit/ -v
```

Expected: ALL tests pass (80+ tests including new test_kimi_backend.py + existing test_backend_registry.py).

**Step 4: Run registry test specifically to confirm 'kimi' registered**

```bash
cd backend && python -m pytest tests/unit/test_backend_registry.py -v
```

Expected: PASS. If test_backend_registry.py has a hardcoded list of expected backends, add "kimi" to it.

**Step 5: Verify via interactive Python**

```bash
cd backend && python -c "from app.backends import BACKEND_REGISTRY; print(sorted(BACKEND_REGISTRY.keys()))"
```

Expected output: `['claude-code', 'codex', 'kimi']`

**Step 6: Commit**

```bash
git add backend/app/backends/__init__.py
git commit -m "feat(backends): register KimiBackend in BACKEND_REGISTRY

Adds 'kimi' to BACKEND_REGISTRY. Frontend SettingsPanel dropdown,
orchestrator backend resolution, and e2e --backend flag all
auto-discover via registry (already backend-neutral).

Available backends: codex / claude-code / kimi"
```

---

## Task 5: Final verification + cleanup

**Step 1: Run full unit test suite**

```bash
cd backend && python -m pytest tests/unit/ -v
```

Expected: ALL tests pass. Total test count should be previous count + 16 (new kimi tests).

**Step 2: Verify SettingsPanel dropdown picks up new backend (manual)**

a. Restart backend if running:
```bash
./start.sh restart
```

b. Restart frontend if running (or just rely on Vite HMR for SettingsPanel).
   SettingsPanel reads backend list from a static config or `/config` API;
   confirm dropdown shows "kimi" alongside "codex" / "claude-code".

c. If SettingsPanel has a hardcoded list of backends (search for "codex" or
   "claude-code" in frontend/src/components/SettingsPanel.tsx), add "kimi":
   ```typescript
   const BACKENDS = ['codex', 'claude-code', 'kimi'];
   ```
   Or, if it fetches from `/config` API, confirm config endpoint returns kimi.

**Step 3: Smoke test (manual, optional but recommended)**

a. Open frontend at http://localhost:5173
b. SettingsPanel: select "kimi" backend
c. Input a simple sample (e.g., 4-col-grad reference image + description)
d. Click Generate
e. Watch AgentLog: should see kimi events flowing (assistant text / tool_call
   names like Read / Bash / ReadMediaFile / tool_result)
f. Wait for completion. Check that `render_final.png` is generated and not blank.
g. Check pipeline_state.json: `backend` field = "kimi".

**Step 4: Update AGENTS.md (worktree-level) with kimi entry**

In `.worktrees/v2.0-codex-od/AGENTS.md`, if there's a backends section that
lists supported backends, add kimi. If no such section exists, skip.

**Step 5: Commit final state**

```bash
git status
# If SettingsPanel.tsx changed:
git add frontend/src/components/SettingsPanel.tsx
git commit -m "feat(frontend): add kimi option to SettingsPanel dropdown"
```

---

## Rollback

If any task fails and you want to roll back:

```bash
git log --oneline -10
# Identify the kimi-related commits
git reset --hard <pre-kimi-commit>
```

Or selectively revert:
```bash
git revert <commit-hash>
```

---

## Out of Scope (explicit non-goals)

These are listed in the spec but called out here so the implementer does NOT
do them as part of this plan:

- ❌ 20-sample kimi benchmark (separate work item)
- ❌ Token usage compatibility shim (kimi has no usage; accept None)
- ❌ Future-proofing for kimi v0.29+ breaking changes (track separately)
- ❌ ACP stdio JSON-RPC integration (YAGNI)
- ❌ Direct Moonshot Platform API integration (loses agent loop)
- ❌ Modifying skills/AGENTS.md or SKILL.md (already backend-neutral)

---

## Estimated Effort

- Task 1 (env var): 2 minutes
- Task 2 (write tests): 10 minutes
- Task 3 (implement KimiBackend): 10 minutes
- Task 4 (register + verify): 5 minutes
- Task 5 (smoke test): 10 minutes

**Total: ~40 minutes** for a single implementer working sequentially.
