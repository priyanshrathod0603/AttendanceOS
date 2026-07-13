"""Background face-recognition worker for a single video source.

This module replaces the previous ``face_recognition``-based pipeline with
an InsightFace + cosine-similarity matcher. InsightFace embeddings are
already L2-normalised, so we just take the dot product of two embeddings
and compare it against a configurable threshold.
"""
from __future__ import annotations

import os
import platform
import re
import threading
import time
from datetime import date, datetime, timezone
from typing import Optional

import cv2
import numpy as np

from database.db import db
from database.models import Attendance, Student

from .encoder import detect_faces


def _utcnow() -> datetime:
    """Timezone-aware UTC now (replacement for deprecated ``utcnow``)."""
    return datetime.now(timezone.utc)


class FaceRecognizer:
    """Reads one video source in a background thread and matches faces."""

    def __init__(
        self,
        source: str | int,
        threshold: float = 0.35,
        cooldown: int = 300,
        camera_id: Optional[int] = None,
    ) -> None:
        # OpenCV accepts both int device indices and string RTSP URLs.
        self.source: str | int = self._normalize_source(source)
        self.threshold: float = threshold
        self.cooldown: int = cooldown
        self.camera_id: Optional[int] = camera_id

        self.running: bool = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.cap: Optional[cv2.VideoCapture] = None

        # Cached DB state (refreshed on demand).
        self._known_embeddings: list[np.ndarray] = []
        self._known_meta: list[tuple[int, str, str]] = []

        # Per-student "last marked at" timestamps for cooldown.
        self._last_seen: dict[int, datetime] = {}

        self.lock = threading.Lock()
        self.last_frame: Optional[np.ndarray] = None
        self.last_detections: list[dict] = []

    @staticmethod
    def _normalize_source(source: str | int | None) -> str | int:
        """Coerce camera settings into something OpenCV can open.

        Numeric values are preserved as integers. Blank strings, whitespace,
        and random text fall back to the default webcam index ``0``.
        Valid URLs/paths are preserved so RTSP or local video files still work.
        """
        if source is None:
            return 0

        text = str(source).strip()
        if not text:
            return 0

        if re.fullmatch(r"[-+]?\d+", text):
            return int(text)

        if text.startswith(("rtsp://", "rtmp://", "http://", "https://", "file://")):
            if text.startswith(("http://", "https://")):
                temp = text.rstrip("/")
                if not temp.endswith("/video"):
                    text = temp + "/video"
            return text

        if text.startswith("/") or os.path.exists(text):
            return text

        # Anything else is treated as an invalid source label and falls back
        # to the default first camera device. This prevents a whitespace-only
        # or gibberish string from being passed straight into OpenCV.
        return 0

    # ------------------------------------------------------------------ DB
    def refresh_known_faces(self) -> None:
        """Reload embeddings + metadata from the database."""
        students = Student.query.all()
        embeddings: list[np.ndarray] = []
        meta: list[tuple[int, str, str]] = []
        for student in students:
            if student.encoding:
                embeddings.append(np.asarray(student.encoding, dtype=np.float32))
                meta.append((student.id, student.name, student.roll_no))

        with self.lock:
            self._known_embeddings = embeddings
            self._known_meta = meta

    def _mark_attendance(self, student_id: int, similarity: float) -> Optional[Attendance]:
        """Insert one attendance row, respecting per-student cooldown."""
        now = _utcnow()
        last = self._last_seen.get(student_id)
        if last and (now - last).total_seconds() < self.cooldown:
            return None

        already_today = (
            Attendance.query.filter_by(student_id=student_id)
            .filter(db.func.date(Attendance.timestamp) == date.today())
            .first()
        )
        if already_today:
            self._last_seen[student_id] = now
            return None

        record = Attendance(
            student_id=student_id,
            camera_id=self.camera_id,
            timestamp=now,
            confidence=float(similarity),
            status="present",
        )
        db.session.add(record)
        db.session.commit()
        self._last_seen[student_id] = now
        return record

    # -------------------------------------------------------------- per frame
    def _process_frame(self, frame: np.ndarray) -> list[dict]:
        """Run detection + matching on a single frame."""
        # [DEBUG] running detection on the current frame.
        print("[DEBUG] Running detect_faces()")
        # ``detect_faces`` already returns ``(box, embedding)`` pairs.
        faces = detect_faces(frame)
        # [DEBUG] how many faces were detected this frame.
        print(f"[DEBUG] Faces detected={len(faces)}")

        with self.lock:
            known = list(self._known_embeddings)
            meta = list(self._known_meta)

        detections: list[dict] = []
        for (top, right, bottom, left), embedding in faces:
            embedding_np = np.asarray(embedding, dtype=np.float32)

            name, roll, similarity = "Unknown", "-", 0.0
            if known:
                # Cosine similarity == dot product because embeddings are L2-normalised.
                sims = np.asarray(known) @ embedding_np
                best = int(np.argmax(sims))
                if sims[best] >= self.threshold:
                    student_id, student_name, student_roll = meta[best]
                    name, roll = student_name, student_roll
                    similarity = float(sims[best])
                    self._mark_attendance(student_id, similarity)

            detections.append(
                {
                    "name": name,
                    "roll": roll,
                    "confidence": float(similarity),
                    "box": [int(top), int(right), int(bottom), int(left)],
                }
            )
        return detections

    def _open_capture(self) -> bool:
        """Internal helper to open cv2.VideoCapture with correct backend and logs."""
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        print("Camera URL:")
        print(self.source)

        # On macOS the default backend (cv2.CAP_ANY) sometimes fails to open
        # an internal webcam even though CAP_AVFOUNDATION works fine. We pick
        # the backend explicitly per-platform for local webcams, but use the
        # default backend for network streams so FFmpeg/GStreamer is used.
        if platform.system() == "Darwin":
            source = int(self.source) if str(self.source).isdigit() else self.source
            if isinstance(source, int):
                self.cap = cv2.VideoCapture(source, cv2.CAP_AVFOUNDATION)
            else:
                self.cap = cv2.VideoCapture(source)
        else:
            self.cap = cv2.VideoCapture(self.source)

        opened = self.cap.isOpened()
        print(f"Opened={opened}")

        if opened:
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            print(f"FPS={fps}")
            print(f"Frame Width={width}")
            print(f"Frame Height={height}")
            try:
                print("[DEBUG] Backend:", self.cap.getBackendName())
            except Exception:
                print("[DEBUG] Backend: <unavailable>")
        else:
            print(f"[WARN] Camera source could not be opened: {self.source}")

        return opened

    # ----------------------------------------------------------- lifecycle
    def start(self, app) -> None:
        """Spawn the background capture loop."""
        if self.running:
            return

        self._stop_event.clear()
        self.refresh_known_faces()

        if not self._open_capture():
            self.running = False
            return

        # [DEBUG] warm-up loop. Many USB/internal cameras return False for
        # the first few reads while AVFoundation / V4L2 initialises the
        # device. Burning through ~20 frames here lets us fail fast on a
        # genuinely broken source instead of looping forever in _loop().
        warmup_ok = False
        for i in range(20):
            ok, frame = self.cap.read()
            print(f"Frame={ok}")
            if ok and frame is not None:
                warmup_ok = True
                break
        if not warmup_ok:
            print("[DEBUG] Warmup failed: every frame returned False. "
                  "Camera is not producing frames; aborting start().")
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            self.running = False
            return

        self.running = True
        # daemon=True so that even if our shutdown hook somehow fails to
        # run, the worker thread cannot keep the Python process alive and
        # block the port from being released. ``stop()`` is the preferred
        # way to tear the thread down; this is just a safety net.
        self._thread = threading.Thread(
            target=self._loop,
            args=(app,),
            daemon=True,
            name=f"FaceRecognizer-{self.camera_id or self.source}",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background loop and release the capture device.

        Order matters: we *first* release ``self.cap`` (which unblocks the
        blocking ``cap.read()`` call inside the worker thread), *then*
        signal the worker to stop, and only then join. This guarantees the
        worker can actually make progress and exit promptly.
        """
        self.running = False
        self._stop_event.set()
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        thread = self._thread
        self._thread = None
        if thread and thread.is_alive():
            # daemon=True means join() can return even if the thread is
            # still alive, but in practice releasing the capture above
            # makes the worker exit within a few ms. 2s is a hard ceiling.
            thread.join(timeout=2)
        with self.lock:
            self.last_frame = None
            self.last_detections = []

    def _loop(self, app) -> None:
        """Continuously read frames and run face matching."""
        consecutive_failures = 0
        while self.running and not self._stop_event.is_set():
            if self.cap is None:
                print("[DEBUG] Camera capture is None, attempting to reopen...")
                if not self._open_capture():
                    self._stop_event.wait(2.0)
                    continue
                consecutive_failures = 0

            ok, frame = self.cap.read()
            print(f"Frame={ok}")

            if not ok or frame is None:
                consecutive_failures += 1
                print(f"[WARN] Frame read failed (consecutive={consecutive_failures})")

                # Retry immediately up to 3 times
                if consecutive_failures < 3:
                    self._stop_event.wait(0.1)
                    continue

                # Reconnect
                print("[WARN] Too many consecutive frame failures. Releasing and reconnecting...")
                if self.cap is not None:
                    try:
                        self.cap.release()
                    except Exception:
                        pass
                    self.cap = None
                self._stop_event.wait(2.0)
                continue

            consecutive_failures = 0

            try:
                with app.app_context():
                    detections = self._process_frame(frame)
            except Exception:
                # [DEBUG] print the full traceback so we can see exactly
                # which step in the pipeline failed.
                import traceback
                traceback.print_exc()
                detections = []

            with self.lock:
                self.last_frame = frame
                self.last_detections = detections
