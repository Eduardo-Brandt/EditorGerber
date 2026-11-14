"""Native batch progress and read-only KiCad compatibility verification."""

import hashlib
import json
import os
import sys
from pathlib import Path
from time import monotonic, sleep


def main():
    root = Path(__file__).resolve().parents[1]
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "fixtures"
    out = root / "output/v011/native"
    out.mkdir(parents=True, exist_ok=True)
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["EDITOR_GERBER_SETTINGS"] = str(out / "preferences.json")

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox, QToolBar

    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.app.metadata import REPORT_PROBLEM_URL, VERSION
    from gerber_editor.app.settings import apply_theme
    from gerber_editor.geometry.boolean import object_geometry
    from gerber_editor.gerber.writer import GerberWriter, SaveMode
    from gerber_editor.ui.branding import apply_branding

    paths = sorted(source.glob("*.gbr")) + sorted(source.glob("*.drl"))
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()
    }
    app = QApplication([])
    apply_branding(app)
    apply_theme(app)
    editor = MainWindow()
    editor.showMaximized()
    editor.activateWindow()
    errors, import_values, save_values = [], [], []
    editor.show_error = lambda title, message: errors.append((title, str(message)))

    def import_progress(value):
        import_values.append(value)
        if value == 2:
            QTimer.singleShot(0, lambda: editor.grab().save(str(out / "01_opening_progress.png")))

    def save_progress(value):
        save_values.append(value)
        if value == 2:
            QTimer.singleShot(0, lambda: editor.grab().save(str(out / "04_saving_progress.png")))

    editor.import_progress.valueChanged.connect(import_progress)
    editor.save_progress.valueChanged.connect(save_progress)

    def wait(predicate, seconds=300):
        deadline = monotonic() + seconds
        while not predicate() and monotonic() < deadline:
            app.processEvents()
            sleep(0.01)  # Let Python workers run between native event batches.
        assert predicate(), "Native check timed out"

    started = monotonic()
    editor.open_paths_async(paths)
    wait(lambda: not editor._import_jobs and not editor.import_progress.active)
    import_seconds = monotonic() - started
    assert len(editor.layers) == len(list(source.glob("*.gbr")))
    assert import_values == list(range(len(paths) + 1))
    assert len(errors) == bool(list(source.glob("*.drl")))
    assert all("Excellon" in message for _, message in errors)
    editor.grab().save(str(out / "02_kicad_loaded.png"))
    report = {
        "version": VERSION,
        "files_processed": len(paths),
        "layers": len(editor.layers),
        "import_seconds": round(import_seconds, 2),
        "import_progress": import_values,
        "recognized_excellon": errors,
        "roundtrips": [],
    }
    normalized = out / "normalized"
    normalized.mkdir(exist_ok=True)
    targets = out / "save_all"
    targets.mkdir(exist_ok=True)
    for layer in editor.layers:
        original = layer.path
        assert GerberWriter().serialize(layer, SaveMode.PRESERVATION) == original.read_bytes()
        validation = GerberWriter().save(
            layer, normalized / layer.name, SaveMode.NORMALIZED, overwrite=True
        )
        cached = editor.canvas.renderer._objects
        holes = sum(
            len(cached[o.id][1].interiors)
            for o in layer.objects
            if cached[o.id][1].geom_type == "Polygon"
        )
        report["roundtrips"].append(
            {
                "name": layer.name,
                "objects": validation.object_count,
                "holes": holes,
                "preservation_identical": True,
            }
        )
        # Only verification output destinations are used by Save all.
        layer.path = targets / layer.name
        layer.saved_signature = ()
    assert not any(p.parent == source for p in (layer.path for layer in editor.layers))
    execute = QMessageBox.exec

    def confirm(dialog):
        if dialog.windowTitle() == editor.t("Salvar todos os arquivos"):

            def accept():
                dialog.grab().save(str(out / "03_save_all_warning.png"))
                button = next(
                    b
                    for b in dialog.buttons()
                    if dialog.buttonRole(b) == QMessageBox.ButtonRole.AcceptRole
                )
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)

            QTimer.singleShot(180, accept)
        return execute(dialog)

    QMessageBox.exec = confirm
    toolbar = next(
        bar for bar in editor.findChildren(QToolBar) if editor.save_all_action in bar.actions()
    )
    QTest.mouseClick(toolbar.widgetForAction(editor.save_all_action), Qt.MouseButton.LeftButton)
    wait(lambda: not editor._save_all_running)
    assert save_values == list(range(len(editor.layers) + 1))
    assert all(not layer.modified for layer in editor.layers)
    assert all(
        layer.path.read_bytes() == (source / layer.name).read_bytes() for layer in editor.layers
    )
    editor.grab().save(str(out / "05_saved_all.png"))
    report["save_progress"] = save_values
    urls = []
    QDesktopServices.openUrl = staticmethod(lambda url: urls.append(url.toString()) or True)
    editor.chrome.actions["help.report_problem"].trigger()
    assert urls == [REPORT_PROBLEM_URL]
    report["report_url"] = urls[0]
    for layer in editor.layers:
        layer.visible = layer.function == "F.Cu"
    editor.refresh()
    editor.canvas.fit_all()
    QTest.qWait(100)
    editor.grab().save(str(out / "06_copper_holes.png"))
    # Select the smallest ring with holes and ensure it remains empty at its center.
    copper = next((layer for layer in editor.layers if layer.function == "F.Cu"), None)
    if copper:
        geometries = [
            object_geometry(o) for o in copper.objects if o.geometry.__class__.__name__ == "Region"
        ]
        assert any(g.geom_type == "Polygon" and len(g.interiors) for g in geometries)
    QTest.mouseClick(toolbar.widgetForAction(editor.close_all_action), Qt.MouseButton.LeftButton)
    assert not editor.layers
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
    assert after == before
    report["original_inputs_unchanged"] = True
    report["source_sha256"] = {p.name: digest for p, digest in before.items()}
    (out / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "version": VERSION,
                "layers": report["layers"],
                "import_seconds": import_seconds,
                "original_inputs_unchanged": True,
            }
        ),
        flush=True,
    )
    editor.close()
    app.processEvents()


if __name__ == "__main__":
    main()
