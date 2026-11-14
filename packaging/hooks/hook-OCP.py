"""Keep OpenCascade and its native wheel libraries; no Python VTK UI is needed."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, get_package_paths

datas, binaries, hiddenimports = collect_all("OCP", include_py_files=False)
site, package = get_package_paths("OCP")
site = Path(site)
for relative in (
    "cadquery_ocp.libs",
    "vtk.libs",
    "OCP/.dylibs",
    "vtkmodules/.dylibs",
    "vtkmodules",
):
    folder = site / relative
    if folder.is_dir():
        for path in folder.rglob("*"):
            if path.is_file() and (
                path.suffix.lower() in (".dll", ".dylib")
                or (
                    ".so" in path.name and (relative != "vtkmodules" or path.name.startswith("lib"))
                )
            ):
                destination = str(path.parent.relative_to(site))
                binaries.append((str(path), destination))
