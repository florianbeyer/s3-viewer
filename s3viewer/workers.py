"""Hintergrundaufgaben, damit die Oberfläche bei S3-Anfragen bedienbar bleibt."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, QTimer, Signal

from s3viewer.s3 import humanize_error


class WorkerSignals(QObject):
    succeeded = Signal(int, object)
    failed = Signal(int, str)


class Worker(QRunnable):
    def __init__(self, ident: int, fn: Callable[[], object]):
        super().__init__()
        self.ident = ident
        self.fn = fn
        self.signals = WorkerSignals()
        self.setAutoDelete(False)

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:
            self.signals.failed.emit(self.ident, humanize_error(exc))
        else:
            self.signals.succeeded.emit(self.ident, result)


class TaskRunner(QObject):
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(4)
        self.pool.setExpiryTimeout(200)
        self._callbacks: dict[int, tuple[Callable[[object], None], Callable[[str], None]]] = {}
        self._workers: dict[int, Worker] = {}
        self._next = 0

    def submit(
        self,
        fn: Callable[[], object],
        on_ok: Callable[[object], None],
        on_err: Callable[[str], None],
    ) -> None:
        self._next += 1
        ident = self._next
        self._callbacks[ident] = (on_ok, on_err)
        worker = Worker(ident, fn)
        self._workers[ident] = worker
        worker.signals.succeeded.connect(self._on_ok, Qt.ConnectionType.QueuedConnection)
        worker.signals.failed.connect(self._on_err, Qt.ConnectionType.QueuedConnection)
        self.pool.start(worker)

    def drop_callbacks(self) -> None:
        self._callbacks.clear()

    def _on_ok(self, ident: int, result: object) -> None:
        callback = self._callbacks.pop(ident, (None, None))[0]
        if callback is not None:
            callback(result)
        QTimer.singleShot(0, lambda ident=ident: self._release(ident))

    def _on_err(self, ident: int, message: str) -> None:
        callback = self._callbacks.pop(ident, (None, None))[1]
        if callback is not None:
            callback(message)
        QTimer.singleShot(0, lambda ident=ident: self._release(ident))

    def _release(self, ident: int) -> None:
        self._workers.pop(ident, None)
