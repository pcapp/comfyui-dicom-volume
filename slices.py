"""Stored-axis float32 planes and a bounded reference registry, independent of the host."""

from collections import OrderedDict
from dataclasses import dataclass
from numbers import Integral
import secrets
import threading
import time

import numpy as np


# (fixed voxel axis, horizontal voxel axis, vertical voxel axis), in x,y,z.
PLANES = {"axial": (2, 0, 1), "coronal": (1, 0, 2), "sagittal": (0, 1, 2)}


def plane_geometry(volume, axis):
    if axis not in PLANES:
        raise ValueError("Invalid axis.")
    fixed, horizontal, vertical = PLANES[axis]
    shape = volume.voxels.shape[::-1]
    direction = np.asarray(volume.direction).reshape(3, 3)
    return {
        "width": int(shape[horizontal]), "height": int(shape[vertical]),
        "count": int(shape[fixed]),
        "spacing": [volume.spacing[horizontal], volume.spacing[vertical]],
        "axes": [fixed, horizontal, vertical],
        "flip_x": False, "flip_y": axis != "axial",
        "right_lps": direction[:, horizontal].tolist(),
        "down_lps": (direction[:, vertical] * (1 if axis == "axial" else -1)).tolist(),
    }


def pixel_to_voxel(volume, axis, index, column, row):
    geometry = plane_geometry(volume, axis)
    for value, size in zip((index, column, row),
                           (geometry["count"], geometry["width"], geometry["height"])):
        if isinstance(value, bool) or not isinstance(value, Integral) or not 0 <= value < size:
            raise ValueError("Index out of range.")
    fixed, horizontal, vertical = PLANES[axis]
    xyz = [0, 0, 0]
    xyz[fixed] = index
    xyz[horizontal] = column
    xyz[vertical] = geometry["height"] - 1 - row if geometry["flip_y"] else row
    return tuple(xyz)


def extract_slice(volume, axis, index):
    """Unflipped row-major plane; flip flags describe display, never transport."""
    pixel_to_voxel(volume, axis, index, 0, 0)
    if axis == "axial":
        plane = volume.voxels[index, :, :]
    elif axis == "coronal":
        plane = volume.voxels[:, index, :]
    else:
        plane = volume.voxels[:, :, index]
    return np.ascontiguousarray(plane, dtype="<f4")


def volume_descriptor(volume, handle):
    return {"handle": handle, "dtype": "float32", "byte_order": "little",
            "planes": {axis: plane_geometry(volume, axis) for axis in PLANES}}


@dataclass
class _Entry:
    handle: str
    touched: float
    volume: object = None


class VolumeRegistry:
    """LRU references only, shared by identical source manifests. Never owns voxel copies.

    Reserving a generation during fingerprinting makes eviction observable to the
    graph cache. A later run then executes the loader even with unchanged files.
    All operations are locked: host execution and HTTP run on different threads.
    """

    def __init__(self, max_count=8, max_bytes=1024**3, ttl=600, clock=time.monotonic):
        if max_count < 1 or max_bytes < 1 or ttl <= 0:
            raise ValueError("Registry limits must be positive.")
        self.max_count, self.max_bytes, self.ttl = max_count, max_bytes, ttl
        self.clock = clock
        self._entries = OrderedDict()
        self._lock = threading.RLock()

    def _prune(self):
        now = self.clock()
        for key, entry in list(self._entries.items()):
            if now - entry.touched >= self.ttl:
                del self._entries[key]

    def prune(self):
        with self._lock:
            self._prune()

    @property
    def retained_bytes(self):
        with self._lock:
            return sum(e.volume.voxels.nbytes for e in self._entries.values() if e.volume is not None)

    def reserve(self, fingerprint):
        with self._lock:
            self._prune()
            entry = self._entries.get(fingerprint)
            if entry is None:
                while len(self._entries) >= self.max_count:
                    self._entries.popitem(last=False)
                entry = _Entry(secrets.token_hex(24), self.clock())
                self._entries[fingerprint] = entry
            entry.touched = self.clock()
            self._entries.move_to_end(fingerprint)
            return entry.handle

    def register(self, fingerprint, volume):
        with self._lock:
            handle = self.reserve(fingerprint)
            if volume.voxels.nbytes > self.max_bytes:
                # Keep only the small reservation so oversized volumes still cache.
                return None
            self._entries[fingerprint].volume = volume
            while self.retained_bytes > self.max_bytes:
                self._entries.popitem(last=False)
            return handle

    def get(self, handle):
        with self._lock:
            self._prune()
            for key, entry in self._entries.items():
                if entry.handle == handle and entry.volume is not None:
                    entry.touched = self.clock()
                    self._entries.move_to_end(key)
                    return entry.volume
            raise KeyError("Volume expired. Run the graph again.")
