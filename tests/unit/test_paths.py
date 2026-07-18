from __future__ import annotations

from pathlib import Path

from app.core.paths import build_paths


def test_build_paths_creates_expected_dirs(tmp_path: Path) -> None:
    paths = build_paths(tmp_path)
    assert paths.root_dir == tmp_path
    assert paths.data_dir.exists()
    assert paths.logs_dir.exists()
    assert paths.db_path.parent == paths.data_dir

