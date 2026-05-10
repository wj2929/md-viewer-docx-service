import shutil
import tempfile
from pathlib import Path


class RenderQueueFull(RuntimeError):
    pass


class RenderRuntime:
    def __init__(self, concurrency: int = 1, queue_max: int = 8):
        self.concurrency = max(1, concurrency)
        self.queue_max = max(0, queue_max)
        self._queued = 0

    def acquire_nowait(self) -> None:
        if self._queued >= self.queue_max:
            raise RenderQueueFull("render queue is full")
        self._queued += 1

    def release(self) -> None:
        self._queued = max(0, self._queued - 1)


def create_output_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="mdv-render-")).resolve()


def cleanup_output_dir(output_dir: Path) -> None:
    shutil.rmtree(output_dir, ignore_errors=True)


def assert_output_path_inside(output_dir: Path, path: Path) -> Path:
    resolved_output_dir = output_dir.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_output_dir and resolved_output_dir not in resolved_path.parents:
        raise ValueError(f"renderer output path is outside output directory: {resolved_path}")
    return resolved_path
