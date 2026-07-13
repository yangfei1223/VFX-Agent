"""Pipeline state persistence (v2.0).

Simple JSON file storage, one file per pipeline_id.
Replaces v1.0's PipelineState 4-region (baseline/snapshot/gradient_window/checkpoint).
v2.0 codex manages these in workdir via files; Python only mirrors final state.
"""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
from typing import Optional


@dataclass
class PipelineRecord:
    """Final state record for a v2.0 pipeline run."""
    pipeline_id: str
    status: str  # running | passed | failed | timeout | max_iterations
    workdir: str
    keyframe_paths: list[str]
    final_shader: str = ""
    final_score: float = 0.0
    evaluation: Optional[dict] = None
    codex_usage: Optional[dict] = None  # token stats from JSONL
    duration_ms: int = 0
    error: Optional[str] = None
    events: list[dict] = field(default_factory=list)  # key JSONL events


class StateStore:
    """JSON-file-based persistence. One file per pipeline_id."""
    STORE_DIR: Path = Path("app/pipeline_states")

    @classmethod
    def save(cls, record: PipelineRecord) -> None:
        cls.STORE_DIR.mkdir(parents=True, exist_ok=True)
        path = cls.STORE_DIR / f"{record.pipeline_id}.json"
        path.write_text(json.dumps(asdict(record), indent=2, default=str))

    @classmethod
    def load(cls, pipeline_id: str) -> Optional[PipelineRecord]:
        path = cls.STORE_DIR / f"{pipeline_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return PipelineRecord(**data)

    @classmethod
    def delete(cls, pipeline_id: str) -> None:
        path = cls.STORE_DIR / f"{pipeline_id}.json"
        if path.exists():
            path.unlink()
