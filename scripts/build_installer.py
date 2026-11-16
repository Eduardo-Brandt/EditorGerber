"""Create a native installer from a verified portable build on the target OS."""

import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.build_portable import ROOT, VERSION, platform_name


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def windows_installer(payload, output):
    compiler = shutil.which("ISCC") or str(
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        / "Inno Setup 6/ISCC.exe"
    )
    if not Path(compiler).is_file():
        raise RuntimeError("Install Inno Setup 6 to build the Windows installer")
    run(
        compiler,
        f"/DAppVersion={VERSION}",
        f"/DPayloadDir={payload}",
        f"/DReleaseDir={output}",
        ROOT / "packaging/windows.iss",
    )
    return output / f"EditorGerber-v{VERSION}-setup-windows-x64.exe"


def linux_installer(payload, output, job):
    stage = job / "deb-root"
    application = stage / "opt/editorgerber"
    shutil.copytree(payload, application, symlinks=True)
    binaries = stage / "usr/bin"
    binaries.mkdir(parents=True)
    launcher = binaries / "editorgerber"
    launcher.write_text('#!/bin/sh\nexec /opt/editorgerber/EditorGerber "$@"\n', encoding="utf-8")
    launcher.chmod(0o755)
    desktop = stage / "usr/share/applications"
    desktop.mkdir(parents=True)
    shutil.copy2(ROOT / "packaging/editorgerber.desktop", desktop)
    run("desktop-file-validate", desktop / "editorgerber.desktop")
    icons = stage / "usr/share/pixmaps"
    icons.mkdir(parents=True)
    shutil.copy2(ROOT / "gerber_editor/assets/app_icon.png", icons / "editorgerber.png")
    docs = stage / "usr/share/doc/editorgerber"
    docs.mkdir(parents=True)
    shutil.copy2(ROOT / "COPYRIGHT.md", docs / "copyright")
    control = stage / "DEBIAN"
    control.mkdir()
    installed_kb = (sum(p.stat().st_size for p in stage.rglob("*") if p.is_file()) + 1023) // 1024
    (control / "control").write_text(
        f"Package: editorgerber\nVersion: {VERSION}\nArchitecture: amd64\n"
        "Section: electronics\nPriority: optional\n"
        "Maintainer: Eduardo Guilherme Brandt <eduardogbrandt@yahoo.com.br>\n"
        f"Installed-Size: {installed_kb}\n"
        "Depends: libc6 (>= 2.35), libgl1, libegl1, libopengl0, libx11-6, libxcb1, libxkbcommon0\n"
        "Homepage: https://brandttecnologia.com.br/EditorGerber\n"
        "Description: Gerber and Excellon editor with a 3D PCB viewer\n"
        " Includes Python, Qt, geometry libraries, local help and STEP export.\n",
        encoding="utf-8",
    )
    archive = output / f"EditorGerber-v{VERSION}-setup-linux-x64.deb"
    run("dpkg-deb", "-Zgzip", "-z6", "--root-owner-group", "--build", stage, archive)
    version = subprocess.check_output(["dpkg-deb", "--field", str(archive), "Version"], text=True)
    assert version.strip() == VERSION
    return archive


def macos_installer(payload, output, job):
    stage = job / "pkg-root"
    application = stage / "Applications/EditorGerber.app"
    application.parent.mkdir(parents=True)
    shutil.copytree(payload / "EditorGerber.app", application, symlinks=True)
    resources = application / "Contents/Resources/Distribution"
    resources.mkdir()
    for name in ("LICENSE", "COPYRIGHT.md", "DISTRIBUICAO.md", "BUILD-INFO.json", "VERIFICATION.json"):
        shutil.copy2(payload / name, resources / name)
    shutil.copytree(payload / "THIRD_PARTY_LICENSES", resources / "THIRD_PARTY_LICENSES")
    run("codesign", "--force", "--deep", "--sign", "-", application)
    run("codesign", "--verify", "--deep", "--strict", application)
    components = job / "components.plist"
    run("pkgbuild", "--analyze", "--root", stage, components)
    with components.open("rb") as stream:
        entries = plistlib.load(stream)
    for entry in entries:
        entry["BundleIsRelocatable"] = False
        entry["BundleIsVersionChecked"] = True
        entry["BundleOverwriteAction"] = "upgrade"
    with components.open("wb") as stream:
        plistlib.dump(entries, stream)
    archive = output / f"EditorGerber-v{VERSION}-setup-{platform_name()}.pkg"
    run(
        "pkgbuild", "--root", stage, "--component-plist", components,
        "--identifier", "br.com.brandttecnologia.editorgerber.pkg",
        "--version", VERSION, "--install-location", "/", archive,
    )
    return archive


def verify_installation(archive, job):
    # Install only on a disposable GitHub runner, never into the developer's profile.
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Installation verification must run on a disposable GitHub runner")
    if sys.platform == "win32":
        installed = job / "installed/Editor Gerber"
        run(
            archive, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
            f"/DIR={installed}", f"/LOG={job / 'installer.log'}",
        )
        executable = installed / "EditorGerber.exe"
    elif sys.platform == "linux":
        run("sudo", "apt-get", "install", "-y", archive)
        executable = Path("/usr/bin/editorgerber")
    else:
        assert not Path("/Applications/EditorGerber.app").exists()
        run("sudo", "installer", "-pkg", archive, "-target", "/")
        executable = Path("/Applications/EditorGerber.app/Contents/MacOS/EditorGerber")
    report = job / "installer-verification"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    run(executable, "--verify-package", report, cwd=job, env=environment, timeout=240)
    result = json.loads((report / "report.json").read_text(encoding="utf-8"))
    assert result.get("success") and result.get("frozen") and result.get("version") == VERSION
    if sys.platform == "win32":
        run(
            installed / "unins000.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
            f"/LOG={job / 'uninstaller.log'}",
        )
        assert not executable.exists(), "Uninstaller left the application executable behind"
    elif sys.platform == "linux":
        run("sudo", "dpkg", "--remove", "editorgerber")
        assert not executable.exists(), "Package removal left the application launcher behind"
    print(json.dumps({"installer_verified": True, "platform": platform_name(), **result}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-installation", action="store_true")
    args = parser.parse_args()
    system = platform_name()
    output = ROOT / "dist"
    payload = output / f"EditorGerber-v{VERSION}-{system}"
    if payload.resolve().parent != output.resolve() or output.resolve().parent != ROOT.resolve():
        raise RuntimeError("Package output must stay inside the project")
    verification = json.loads((payload / "VERIFICATION.json").read_text(encoding="utf-8"))
    assert verification.get("frozen") and verification.get("success")
    assert verification.get("version") == VERSION
    build_root = ROOT / "build"
    if build_root.resolve().parent != ROOT.resolve():
        raise RuntimeError("Build directory must stay inside the project")
    job = Path(tempfile.mkdtemp(prefix="installer-", dir=build_root))
    if sys.platform == "win32":
        archive = windows_installer(payload, output)
    elif sys.platform == "linux":
        archive = linux_installer(payload, output, job)
    else:
        archive = macos_installer(payload, output, job)
    if args.verify_installation:
        verify_installation(archive, job)
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    (output / (archive.name + ".sha256")).write_text(
        f"{digest}  {archive.name}\n", encoding="ascii", newline="\n"
    )
    print(json.dumps({"installer": str(archive), "sha256": digest}), flush=True)


if __name__ == "__main__":
    main()
