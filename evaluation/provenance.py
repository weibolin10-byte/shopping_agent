"""Canonical, reproducible evaluation run manifests."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_sha(root: str | Path = ".") -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


_FINGERPRINT_EXCLUDES = {"README.md", "domains/china_ecommerce/eval/reports/current.json"}


def working_tree_fingerprint(root: str | Path = ".") -> tuple[bool | None, str | None]:
    """Hash tracked diffs plus untracked source files, excluding generated report surfaces."""
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--binary", "HEAD", "--", ".",
             ":(exclude)README.md",
             ":(exclude)domains/china_ecommerce/eval/reports/current.json"],
            cwd=root, stderr=subprocess.DEVNULL,
        )
        untracked_raw = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=root, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None, None
    untracked = [path.decode() for path in untracked_raw.split(b"\0") if path]
    untracked = sorted(path for path in untracked if path not in _FINGERPRINT_EXCLUDES)
    digest = hashlib.sha256()
    digest.update(diff)
    root_path = Path(root)
    for relative in untracked:
        path = root_path / relative
        if path.is_file():
            digest.update(relative.encode())
            digest.update(bytes.fromhex(sha256_file(path)))
    dirty = bool(diff or untracked)
    return dirty, digest.hexdigest() if dirty else None


@dataclass(frozen=True)
class EvaluationManifest:
    run_id: str
    generated_at: float
    git_sha: str
    git_dirty: bool | None
    working_tree_hash: str | None
    domain: str
    dataset_hashes: dict[str, str]
    models: dict[str, str]
    knowledge_version: str
    parameters: dict = field(default_factory=dict)
    seed: int = 42
    report_kind: str = "offline_evaluation"

    def as_dict(self) -> dict:
        return asdict(self)


def build_manifest(*, domain: str, dataset_paths: list[str | Path], models: dict[str, str],
                   knowledge_version: str, parameters: dict | None = None, seed: int = 42,
                   root: str | Path = ".") -> EvaluationManifest:
    root_path = Path(root).resolve()
    hashes = {}
    for path in dataset_paths:
        if not os.path.isfile(path):
            continue
        resolved = Path(path).resolve()
        try:
            key = str(resolved.relative_to(root_path))
        except ValueError:
            key = str(resolved)
        hashes[key] = sha256_file(resolved)
    stamp = int(time.time())
    sha = git_sha(root)
    dirty, tree_hash = working_tree_fingerprint(root)
    return EvaluationManifest(run_id=f"{domain}-{sha[:8]}-{stamp}", generated_at=time.time(),
                              git_sha=sha, git_dirty=dirty, working_tree_hash=tree_hash,
                              domain=domain, dataset_hashes=hashes, models=models,
                              knowledge_version=knowledge_version,
                              parameters=parameters or {}, seed=seed)


def write_canonical_report(path: str | Path, *, manifest: EvaluationManifest,
                           results: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps({"manifest": manifest.as_dict(), "results": results},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, target)
