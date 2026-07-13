"""Manage live recognizers per camera and expose MJPEG snapshots.

Kept API-compatible with the previous module: the Flask route in
``app.py`` still calls ``manager.start(camera, app)``,
``manager.stop(cid)``, ``manager.snapshot(cid)`` and
``manager.refresh_known()``.
"""
from __future__ import annotations

import threading
from typing import Optional

from recognition.recognizer import FaceRecognizer


class RecognitionManager:
    """Holds one ``FaceRecognizer`` per active camera."""

    def __init__(self) -> None:
        self.recognizers: dict[int, FaceRecognizer] = {}
        self._apps: dict[int, object] = {}
        self.lock = threading.Lock()
        self.shutting_down = threading.Event()

    def start(self, camera, app) -> FaceRecognizer:
        """Start (or return) the recognizer for ``camera``."""
        if self.shutting_down.is_set():
            raise RuntimeError("recognition manager is shutting down")
        with self.lock:
            existing = self.recognizers.get(camera.id)
            if existing is not None:
                return existing

            recognizer = FaceRecognizer(
                source=camera.source,
                threshold=0.35,
                cooldown=300,
                camera_id=camera.id,
            )
            try:
                recognizer.start(app)
            except Exception as exc:
                print(f"[WARN] camera {camera.id} could not be started: {exc}")
                return recognizer
            self.recognizers[camera.id] = recognizer
            self._apps[camera.id] = app
            return recognizer

    def stop(self, camera_id: int) -> None:
        with self.lock:
            recognizer = self.recognizers.pop(camera_id, None)
            self._apps.pop(camera_id, None)
        if recognizer is not None:
            recognizer.stop()

    def stop_all(self) -> None:
        """Stop every recognizer and release all camera resources.

        Safe to call multiple times: the second call is a cheap no-op.
        """
        if self.shutting_down.is_set() and not self.recognizers:
            return
        self.shutting_down.set()
        with self.lock:
            recognizers = list(self.recognizers.values())
            apps = list(self._apps.values())
            self.recognizers.clear()
            self._apps.clear()
        for recognizer in recognizers:
            try:
                recognizer.stop()
            except Exception:
                # Never let a single bad recognizer prevent the rest of
                # the shutdown from completing.
                pass
        # Drop our last references to the Flask app objects so any
        # SQLAlchemy engines that may still be attached can be GC'd.
        del apps

    def reset_shutdown(self) -> None:
        """Allow a fresh in-process test app to start recognizers again."""
        self.shutting_down.clear()

    def is_running(self, camera_id: int) -> bool:
        return camera_id in self.recognizers and not self.shutting_down.is_set()

    def snapshot(self, camera_id: int) -> tuple[Optional[object], list[dict]]:
        recognizer = self.recognizers.get(camera_id)
        if recognizer is None:
            return None, []
        # [DEBUG] show whether the recognizer has produced a frame yet
        # and how many detections it has stored.
        print(
            f"[DEBUG] snapshot frame={'YES' if recognizer.last_frame is not None else 'NO'} "
            f"detections={len(recognizer.last_detections)}"
        )
        with recognizer.lock:
            return recognizer.last_frame, recognizer.last_detections

    def refresh_known(self) -> None:
        """Tell every running recognizer to reload its embeddings."""
        with self.lock:
            for recognizer in self.recognizers.values():
                recognizer.refresh_known_faces()


manager = RecognitionManager()
