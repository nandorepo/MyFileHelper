from __future__ import annotations

import shutil


def clean_upload_dirs(upload_config) -> None:
    for path in (upload_config.upload_dir, upload_config.chunk_dir):
        if path.exists():
            try:
                shutil.rmtree(path)
            except OSError:
                # Best-effort cleanup when a full rmtree fails on Windows.
                for child in path.glob("*"):
                    try:
                        if child.is_dir():
                            shutil.rmtree(child, ignore_errors=True)
                        else:
                            child.unlink(missing_ok=True)
                    except OSError:
                        continue
        path.mkdir(parents=True, exist_ok=True)
