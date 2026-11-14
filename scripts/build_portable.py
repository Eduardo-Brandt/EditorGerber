"""Build and verify the native portable package, then create a release archive."""

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gerber_editor.app.metadata import VERSION  # noqa: E402


def platform_name():
    arch = "arm64" if platform.machine().lower() in ("aarch64", "arm64") else "x64"
    return {"win32": "windows", "linux": "linux", "darwin": "macos"}[sys.platform] + "-" + arch


def copy_licenses(target):
    """Retain the wheel license files, not just a package-name list."""
    from packaging.requirements import Requirement

    pending = [
        "PySide6-Essentials",
        "shiboken6",
        "numpy",
        "shapely",
        "qrcode",
        "cadquery-ocp",
        "pillow",
    ]
    seen, versions = set(), {}
    while pending:
        name = pending.pop()
        key = name.lower().replace("_", "-")
        if key in seen:
            continue
        seen.add(key)
        dist = metadata.distribution(name)
        versions[dist.metadata["Name"]] = dist.version
        for dependency in dist.requires or ():
            req = Requirement(dependency)
            if req.marker is None or req.marker.evaluate():
                pending.append(req.name)
        for entry in dist.files or ():
            if any(
                token in entry.name.upper()
                for token in ("LICENSE", "COPYING", "NOTICE", "COPYRIGHT")
            ):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    dest = target / key / str(entry).replace("..", "_")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)
    for source in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE"):
        if source.is_file():
            shutil.copy2(source, target / "Python-LICENSE.txt")
            break
    return versions


def source_archive(destination):
    """Publish only project files; exclude private notes, input data and builds."""
    roots = ["gerber_editor", "scripts", "tests", "fixtures", "packaging", ".github"]
    files = [
        p
        for name in roots
        for p in (ROOT / name).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".log")
    ]
    files += [
        p
        for p in ROOT.iterdir()
        if p.is_file()
        and (
            p.suffix in (".md", ".toml", ".bat", ".ps1")
            or p.name.startswith("requirements")
            or p.name in ("LICENSE", ".gitignore", ".gitattributes")
        )
    ]
    with ZipFile(destination, "w", ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(set(files)):
            archive.write(path, "EditorGerber-source/" + path.relative_to(ROOT).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-verification",
        action="store_true",
        help="Local debugging only; never use for release",
    )
    args = parser.parse_args()
    system = platform_name()
    build_root = ROOT / "build"
    build_root.mkdir(exist_ok=True)
    if build_root.resolve().parent != ROOT.resolve():
        raise RuntimeError("Build directory must stay inside the project")
    job = Path(tempfile.mkdtemp(prefix="portable-", dir=build_root))
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(build_root / "pyinstaller-cache")
    env.setdefault("MACOSX_DEPLOYMENT_TARGET", "14.0")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--workpath",
            str(job / "work"),
            "--distpath",
            str(job / "dist"),
            str(ROOT / "packaging/editor_gerber.spec"),
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    if output.resolve().parent != ROOT.resolve():
        raise RuntimeError("Distribution directory must stay inside the project")
    name = f"EditorGerber-v{VERSION}-{system}"
    payload = output / name
    if payload.exists():
        # This is the single generated package directory, never the dist root.
        if (
            payload.resolve().parent != output.resolve()
            or payload.is_symlink()
            or getattr(payload, "is_junction", lambda: False)()
        ):
            raise RuntimeError("Unsafe package output path")
        shutil.rmtree(payload)
    payload.mkdir()
    if sys.platform == "darwin":
        shutil.copytree(job / "dist/EditorGerber.app", payload / "EditorGerber.app", symlinks=True)
        executable = payload / "EditorGerber.app/Contents/MacOS/EditorGerber"
    else:
        shutil.copytree(job / "dist/EditorGerber", payload, dirs_exist_ok=True)
        executable = payload / ("EditorGerber.exe" if sys.platform == "win32" else "EditorGerber")
    for filename in ("LICENSE", "COPYRIGHT.md", "DISTRIBUICAO.md"):
        shutil.copy2(ROOT / filename, payload / filename)
    versions = copy_licenses(payload / "THIRD_PARTY_LICENSES")
    (payload / "BUILD-INFO.json").write_text(
        json.dumps(
            {
                "version": VERSION,
                "platform": system,
                "python": platform.python_version(),
                "packages": versions,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if not args.skip_verification:
        report = job / "verification"
        subprocess.run(
            [str(executable), "--verify-package", str(report)], cwd=job, timeout=240, check=True
        )
        result = json.loads((report / "report.json").read_text(encoding="utf-8"))
        if not result.get("success") or not result.get("frozen"):
            raise RuntimeError(result)
        shutil.copy2(report / "report.json", payload / "VERIFICATION.json")
    if sys.platform == "darwin":
        archive = output / (name + ".zip")
        subprocess.run(
            ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(payload), str(archive)],
            check=True,
        )
    elif sys.platform == "linux":
        archive = Path(
            shutil.make_archive(str(output / name), "gztar", root_dir=output, base_dir=name)
        )
    else:
        archive = Path(
            shutil.make_archive(str(output / name), "zip", root_dir=output, base_dir=name)
        )
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / (archive.name + ".sha256")).write_text(
        f"{digest}  {archive.name}\n", encoding="ascii"
    )
    source = output / f"EditorGerber-v{VERSION}-source.zip"
    source_archive(source)
    (output / (source.name + ".sha256")).write_text(
        f"{hashlib.sha256(source.read_bytes()).hexdigest()}  {source.name}\n", encoding="ascii"
    )
    print(
        json.dumps(
            {"archive": str(archive), "executable": str(executable), "sha256": digest}, indent=2
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
