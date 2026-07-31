from pathlib import Path

from app.domain.ports import ArtifactStoragePort


class LocalArtifactStorage(ArtifactStoragePort):
    """Local controlled-volume adapter with traversal-safe namespace segments."""

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()

    def write_bytes(self, namespace: list[str], filename: str, content: bytes) -> str:
        if not namespace or any(not item or Path(item).name != item for item in namespace):
            raise ValueError("artifact namespace must contain plain path segments")
        if Path(filename).name != filename:
            raise ValueError("artifact filename must be a plain path segment")
        target_dir = self._root.joinpath(*namespace)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        target.write_bytes(content)
        return str(target)

    def read_text(self, uri: str) -> str:
        path = Path(uri).resolve()
        if self._root not in path.parents:
            raise ValueError("artifact uri escapes configured root")
        return path.read_text(encoding="utf-8")
