from pathlib import Path

import pytest

from app.render_runtime import RenderQueueFull, RenderRuntime, assert_output_path_inside


def test_render_runtime_rejects_when_queue_is_full():
    runtime = RenderRuntime(concurrency=1, queue_max=0)

    with pytest.raises(RenderQueueFull):
        runtime.acquire_nowait()


def test_rejects_renderer_output_outside_output_dir(tmp_path):
    output_dir = tmp_path / "render"
    output_dir.mkdir()
    outside = tmp_path / "outside.png"

    with pytest.raises(ValueError):
        assert_output_path_inside(output_dir, outside)


def test_accepts_renderer_output_inside_output_dir(tmp_path):
    output_dir = tmp_path / "render"
    output_dir.mkdir()
    inside = output_dir / "chart.png"

    assert assert_output_path_inside(output_dir, inside) == Path(inside).resolve()
