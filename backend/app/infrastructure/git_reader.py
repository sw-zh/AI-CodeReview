import hashlib
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings
from app.domain.errors import DomainError
from app.domain.ports import FrozenGitDiff, FrozenGitRange, GitReaderPort


class ReadOnlyGitReader(GitReaderPort):
    """Uses a restricted Git command allowlist in the controlled artifact volume."""

    def freeze_range(self, repository_url: str, base_ref: str, target_ref: str, diff_mode: str, include_paths: list[str], exclude_paths: list[str]) -> FrozenGitRange:
        parsed = urlparse(repository_url)
        if parsed.scheme not in {"https", "ssh"} or not parsed.netloc:
            raise DomainError("GIT_RANGE_INVALID", "仓库地址必须是 https 或 ssh 远程地址")
        if diff_mode not in {"TWO_DOT", "THREE_DOT"}:
            raise DomainError("GIT_RANGE_INVALID", "Diff 模式必须是 TWO_DOT 或 THREE_DOT")
        repository = self._ensure_read_only_clone(repository_url)
        base_sha = self._run(repository, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
        target_sha = self._run(repository, "rev-parse", "--verify", f"{target_ref}^{{commit}}")
        merge_base_sha = self._run(repository, "merge-base", base_sha, target_sha)
        comparison = f"{base_sha}..{target_sha}" if diff_mode == "TWO_DOT" else f"{merge_base_sha}..{target_sha}"
        pathspecs = [*include_paths, *(f":(exclude){path}" for path in exclude_paths)]
        suffix = ("--", *pathspecs) if pathspecs else ()
        diff = self._run(repository, "diff", "--no-ext-diff", "--find-renames", "--binary", comparison, *suffix)
        name_status = self._run(repository, "diff", "--no-ext-diff", "--find-renames", "--name-status", comparison, *suffix)
        coverage = {
            "comparison": comparison,
            "changedFiles": [line for line in name_status.splitlines() if line],
            "includePaths": include_paths,
            "excludePaths": exclude_paths,
            "skipped": [],
        }
        return FrozenGitRange(
            base_sha=base_sha,
            target_sha=target_sha,
            merge_base_sha=merge_base_sha,
            diff_hash=f"sha256:{hashlib.sha256(diff.encode('utf-8')).hexdigest()}",
            coverage=coverage,
        )

    def read_frozen_diff(
        self,
        repository_url: str,
        *,
        base_sha: str,
        target_sha: str,
        merge_base_sha: str,
        diff_mode: str,
        include_paths: list[str],
        exclude_paths: list[str],
        expected_diff_hash: str,
    ) -> FrozenGitDiff:
        """Re-read the range using frozen SHAs, never the user-selected branch names."""
        repository = self._ensure_read_only_clone(repository_url)
        self._run(repository, "cat-file", "-e", f"{base_sha}^{{commit}}")
        self._run(repository, "cat-file", "-e", f"{target_sha}^{{commit}}")
        comparison = f"{base_sha}..{target_sha}" if diff_mode == "TWO_DOT" else f"{merge_base_sha}..{target_sha}"
        pathspecs = [*include_paths, *(f":(exclude){path}" for path in exclude_paths)]
        suffix = ("--", *pathspecs) if pathspecs else ()
        diff = self._run(repository, "diff", "--no-ext-diff", "--find-renames", "--binary", comparison, *suffix)
        actual_hash = f"sha256:{hashlib.sha256(diff.encode('utf-8')).hexdigest()}"
        if actual_hash != expected_diff_hash:
            raise DomainError("INPUT_STALE", "冻结 Git 差异校验失败，不能使用已变化的输入继续分析")
        name_status = self._run(repository, "diff", "--no-ext-diff", "--find-renames", "--name-status", comparison, *suffix)
        return FrozenGitDiff(
            diff=diff,
            coverage={
                "comparison": comparison,
                "changedFiles": [line for line in name_status.splitlines() if line],
                "includePaths": include_paths,
                "excludePaths": exclude_paths,
                "skipped": [],
            },
        )

    def _ensure_read_only_clone(self, repository_url: str) -> Path:
        root = Path(get_settings().artifact_root).resolve() / "repositories"
        root.mkdir(parents=True, exist_ok=True)
        target = root / hashlib.sha256(repository_url.encode("utf-8")).hexdigest()
        if not (target / ".git").exists():
            self._run(root, "clone", "--no-checkout", "--filter=blob:none", repository_url, str(target))
        else:
            self._run(target, "fetch", "--prune", "origin")
        return target

    @staticmethod
    def _run(cwd: Path, *args: str) -> str:
        environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        command = ["git", "-c", "core.hooksPath=/dev/null", "-C", str(cwd), *args]
        try:
            result = subprocess.run(command, capture_output=True, check=True, text=False, timeout=60, env=environment)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise DomainError("GIT_RANGE_INVALID", "无法读取只读 Git 范围") from exc
        return result.stdout.decode("utf-8", errors="replace").strip()
