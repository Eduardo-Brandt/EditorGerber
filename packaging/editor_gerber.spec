"""Native onedir builds. Run through scripts.build_portable on each target OS."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
sys.path.insert(0, str(root))
from gerber_editor.app.metadata import VERSION

data = collect_data_files("gerber_editor", includes=["assets/*", "locales/*"])
a = Analysis(
    [str(root / "scripts" / "portable_entry.py")],
    pathex=[str(root)],
    binaries=[],
    datas=data,
    hiddenimports=["OCP", "qrcode.image.pil"],
    hookspath=[str(root / "packaging" / "hooks")],
    excludes=["matplotlib", "vtk", "vtkmodules", "pytest", "tkinter", "PyQt5", "PyQt6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="EditorGerber",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    icon=str(root / "gerber_editor" / "assets" / ("app_icon.png" if sys.platform == "darwin" else "app_icon.ico")),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="EditorGerber")
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="EditorGerber.app",
        icon=str(root / "gerber_editor" / "assets" / "app_icon.png"),
        bundle_identifier="br.com.brandttecnologia.editorgerber",
        info_plist={
            "CFBundleDisplayName": "Editor Gerber",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "14.0",
            "NSHighResolutionCapable": True,
        },
    )
