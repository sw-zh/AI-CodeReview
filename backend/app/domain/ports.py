from dataclasses import dataclass


@dataclass(frozen=True)
class FrozenGitRange:
    base_sha: str
    target_sha: str
    merge_base_sha: str
    diff_hash: str
    coverage: dict


class GitReaderPort:
    """Read-only Git boundary; it never executes repository content or hooks."""

    def freeze_range(self, repository_url: str, base_ref: str, target_ref: str, diff_mode: str) -> FrozenGitRange:
        raise NotImplementedError
