"""One verified source archive per version; never include backups or environments."""

import os
import re
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

EXCLUDED = {
    ".venv",
    "Backup",
    "output",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    ".codex",
    ".aws",
}
EXCLUDED_FOLDED = {name.casefold() for name in EXCLUDED}


def backup_project(root: Path, version: str, *, replace=False):
    root = root.resolve()
    if not re.fullmatch(r"\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9.]+)?", version):
        raise ValueError("Invalid version")
    folder = root / "Backup"
    folder.mkdir(exist_ok=True)
    target = folder / f"Editor_Gerber_v{version}.zip"
    if target.exists() and not replace:
        with ZipFile(target) as archive:
            if archive.testzip():
                raise OSError("Backup ZIP inválido.")
        return target
    fd, temporary = tempfile.mkstemp(dir=folder, suffix=".zip.tmp")
    os.close(fd)
    try:
        with ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=6) as archive:
            for directory, names, files in os.walk(root):
                names[:] = sorted(
                    name
                    for name in names
                    if name.casefold() not in EXCLUDED_FOLDED
                    and not name.casefold().endswith(".egg-info")
                    and not (Path(directory) / name).is_symlink()
                    and not getattr(Path(directory) / name, "is_junction", lambda: False)()
                )
                for name in sorted(files):
                    path = Path(directory) / name
                    if path.is_symlink() or path.suffix in (".pyc", ".log"):
                        continue
                    archive.write(path, path.relative_to(root).as_posix())
        with ZipFile(temporary) as archive:
            if archive.testzip():
                raise OSError("Falha ao verificar backup ZIP.")
        os.replace(temporary, target)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    return target


def ensure_version_backup():
    from gerber_editor.app.metadata import VERSION

    root = Path(__file__).resolve().parents[2]
    if (root / "pyproject.toml").is_file() and (root / "Iniciar.ps1").is_file():
        return backup_project(root, VERSION)
    return None
