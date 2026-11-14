"""Per-process application and native-fault logs, including pythonw launches."""

import faulthandler
import logging
import os
import platform
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QtMsgType, qInstallMessageHandler

from gerber_editor.app.metadata import APP_NAME, VERSION


class Diagnostics:
    def __init__(self, folder=None):
        override = os.environ.get("EDITOR_GERBER_LOG_DIR")
        root = Path(__file__).resolve().parents[2]
        default = (
            root / "output" / "logs"
            if (root / "pyproject.toml").is_file()
            else Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)) / "logs"
        )
        self.folder = Path(folder or override or default)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.log_path = self.folder / f"editor_{os.getpid()}.log"
        self.fault_path = self.folder / f"fault_{os.getpid()}.log"
        self.handler = RotatingFileHandler(
            self.log_path, maxBytes=2_000_000, backupCount=2, encoding="utf-8"
        )
        self.handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s")
        )
        self.logger = logging.getLogger()
        self.previous_level = self.logger.level
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.handler)
        self.fault_file = self.fault_path.open("a", encoding="utf-8")
        faulthandler.enable(file=self.fault_file, all_threads=True)
        self.previous_hook = sys.excepthook
        self.previous_thread_hook = threading.excepthook
        self.exception_hook = self._exception
        self.thread_hook = self._thread_exception
        sys.excepthook = self.exception_hook
        threading.excepthook = self.thread_hook
        self.previous_qt_handler = qInstallMessageHandler(self._qt_message)
        logging.info(
            "%s %s starting; Python %s; %s; log=%s; native faults=%s",
            APP_NAME,
            VERSION,
            platform.python_version(),
            platform.platform(),
            self.log_path,
            self.fault_path,
        )

    def _exception(self, kind, value, traceback):
        logging.critical("Unhandled application exception", exc_info=(kind, value, traceback))
        self.handler.flush()

    def _thread_exception(self, args):
        logging.critical(
            "Unhandled worker exception: %s",
            args.thread.name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        self.handler.flush()

    def _qt_message(self, kind, context, message):
        level = {
            QtMsgType.QtDebugMsg: logging.DEBUG,
            QtMsgType.QtInfoMsg: logging.INFO,
            QtMsgType.QtWarningMsg: logging.WARNING,
            QtMsgType.QtCriticalMsg: logging.ERROR,
            QtMsgType.QtFatalMsg: logging.CRITICAL,
        }.get(kind, logging.WARNING)
        logging.getLogger("Qt").log(level, "%s", message)

    def close(self):
        logging.info("Application event loop finished")
        qInstallMessageHandler(self.previous_qt_handler)
        if sys.excepthook is self.exception_hook:
            sys.excepthook = self.previous_hook
        if threading.excepthook is self.thread_hook:
            threading.excepthook = self.previous_thread_hook
        faulthandler.disable()
        self.fault_file.close()
        self.logger.removeHandler(self.handler)
        self.handler.close()
        self.logger.setLevel(self.previous_level)
