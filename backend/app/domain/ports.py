from dataclasses import dataclass


@dataclass(frozen=True)
class FrozenGitRange:
    base_sha: str
    target_sha: str
    merge_base_sha: str
    diff_hash: str
    coverage: dict


@dataclass(frozen=True)
class FrozenGitDiff:
    """The exact, already-frozen diff read again by immutable commit SHA."""

    diff: str
    coverage: dict


class GitReaderPort:
    """Read-only Git boundary; it never executes repository content or hooks."""

    def freeze_range(self, repository_url: str, base_ref: str, target_ref: str, diff_mode: str, include_paths: list[str], exclude_paths: list[str]) -> FrozenGitRange:
        raise NotImplementedError

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
        """Read only an immutable SHA range and reject a changed diff payload."""
        raise NotImplementedError
