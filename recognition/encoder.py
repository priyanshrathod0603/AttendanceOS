"""Face encoder backed by InsightFace (Python 3.14 + Apple Silicon ready).

InsightFace is a modern, actively maintained face recognition toolkit.
It uses ONNX Runtime under the hood, so it ships prebuilt wheels for
Python 3.14 and uses CoreMLExecutionProvider on Apple Silicon -- no
cmake, no dlib, no system build tools required.

Public API (kept compatible with the previous ``face_recognition``-based
implementation so the rest of the project doesn't change):

* ``encode_image(path)``            -> list[float] | None
* ``encode_frame(bgr_numpy_frame)``  -> list[float] | None
* ``detect_faces(bgr_numpy_frame)``  -> list[(box, embedding)]
"""
from __future__ import annotations

import os
import threading
from typing import List, Optional, Tuple

import numpy as np

# Lazy import: insightface pulls in onnxruntime and a bunch of model files
# on first use. We keep a module-level singleton so we don't reload weights
# for every frame.
_APP_LOCK = threading.Lock()
_APP = None  # type: ignore[var-annotated]


def _get_app():
    """Return a process-wide ``FaceAnalysis`` instance (built on demand)."""
    global _APP
    if _APP is not None:
        return _APP

    with _APP_LOCK:
        if _APP is not None:
            return _APP

        # Importing inside the function keeps ``import recognition.encoder``
        # cheap for tools that only want the data classes.
        from insightface.app import FaceAnalysis

        # ``buffalo_l`` is the default high-accuracy model pack. It works on
        # CPU and (on Apple Silicon) automatically uses the CoreML EP.
        # ``providers`` lets us force CPU if the user is on a weird build.
        app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
            allowed_modules=["detection", "recognition"],
        )
        # det_size 640x640 is a good balance between speed and recall on
        # classroom CCTV frames.
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _APP = app
        return _APP


def _to_rgb(frame_bgr: np.ndarray) -> np.ndarray:
    """OpenCV gives us BGR; InsightFace expects RGB."""
    return frame_bgr[:, :, ::-1].copy()


def encode_image(image_path: str) -> Optional[List[float]]:
    """Return the 512-d embedding of the largest face in ``image_path``."""
    if not os.path.exists(image_path):
        return None

    import cv2

    bgr = cv2.imread(image_path)
    if bgr is None:
        return None

    faces = _get_app().get(_to_rgb(bgr))
    if not faces:
        return None
    # Pick the largest face so we don't accidentally encode someone in the
    # background of a group photo.
    biggest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return biggest.normed_embedding.astype(float).tolist()


def encode_frame(frame_bgr: np.ndarray) -> Optional[List[float]]:
    """Return the embedding of the largest face in an OpenCV BGR frame."""
    if frame_bgr is None or frame_bgr.size == 0:
        return None
    faces = _get_app().get(_to_rgb(frame_bgr))
    if not faces:
        return None
    biggest = max(
        faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
    )
    return biggest.normed_embedding.astype(float).tolist()


def detect_faces(frame_bgr: np.ndarray) -> List[Tuple[Tuple[int, int, int, int], List[float]]]:
    """Detect *all* faces in a frame.

    Returns a list of ``((top, right, bottom, left), embedding)`` tuples so
    the recognizer can both draw boxes and compare embeddings.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return []

    faces = _get_app().get(_to_rgb(frame_bgr))
    out: List[Tuple[Tuple[int, int, int, int], List[float]]] = []
    for f in faces:
        x1, y1, x2, y2 = f.bbox.astype(int).tolist()
        out.append(((int(y1), int(x2), int(y2), int(x1)), f.normed_embedding.astype(float).tolist()))
    return out
