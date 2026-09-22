"""Typed anatomy on the source CT grid; no host or model imports."""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import SimpleITK as sitk


LABELS = {int(key): value for key, value in json.loads(
    Path(__file__).with_name("anatomy_labels.json").read_text()).items()}
GROUPS = {
    "both lungs": (10, 11, 12, 13, 14),
    "left lung": (10, 11),
    "right lung": (12, 13, 14),
    "all ribs": tuple(range(92, 116)),
    "thoracic vertebrae": tuple(range(32, 44)),
}
ANATOMY = {name: (key,) for key, name in LABELS.items()} | GROUPS
ANATOMY_OPTIONS = ["heart", "both lungs", "aorta"] + sorted(
    set(ANATOMY) - {"heart", "both lungs", "aorta"})


@dataclass(frozen=True)
class Grid:
    shape: tuple[int, int, int]
    spacing: tuple[float, float, float]
    origin: tuple[float, float, float]
    direction: tuple[float, ...]
    series_uid: str
    source_files: tuple[str, ...]

    @classmethod
    def from_volume(cls, volume):
        return cls(tuple(volume.voxels.shape), tuple(volume.spacing), tuple(volume.origin),
                   tuple(volume.direction), volume.series_uid, tuple(volume.source_files))


@dataclass(frozen=True)
class Segmentation:
    labels: np.ndarray
    grid: Grid
    label_names: dict[int, str]
    provenance: dict


@dataclass(frozen=True)
class VolumeMask:
    mask: np.ndarray
    grid: Grid
    selected_ids: tuple[int, ...]
    selected_names: tuple[str, ...]
    touches_boundary: bool
    provenance: dict


def grid_image(array, grid):
    """SimpleITK handles zyx arrays and writes NIfTI with the LPS -> RAS affine."""
    if array.ndim != 3 or tuple(array.shape) != grid.shape:
        raise ValueError("Array does not match the source grid.")
    image = sitk.GetImageFromArray(array)
    image.SetSpacing(grid.spacing)
    image.SetOrigin(grid.origin)
    image.SetDirection(grid.direction)
    return image


def restore_labels(prediction, grid):
    if prediction.GetDimension() != 3 or prediction.GetNumberOfComponentsPerPixel() != 1:
        raise ValueError("Backend must return a scalar 3D label image.")
    values = sitk.GetArrayFromImage(prediction)
    if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
        raise ValueError("Backend returned non-integer or non-finite labels.")
    if not set(np.unique(values)).issubset({0, *LABELS}):
        raise ValueError("Backend returned labels outside the pinned total catalog.")
    reference = grid_image(np.zeros(grid.shape, dtype=np.uint8), grid)
    same = prediction.GetSize() == reference.GetSize() and all(
        np.allclose(a, b, atol=1e-5, rtol=0) for a, b in (
            (prediction.GetSpacing(), grid.spacing), (prediction.GetOrigin(), grid.origin),
            (prediction.GetDirection(), grid.direction)))
    if not same:
        prediction = sitk.Resample(prediction, reference, sitk.Transform(),
                                  sitk.sitkNearestNeighbor, 0, sitk.sitkUInt8)
    labels = sitk.GetArrayFromImage(prediction).astype(np.uint8)
    labels.setflags(write=False)
    return labels


def select_anatomy(segmentation, anatomy):
    if anatomy not in ANATOMY:
        raise ValueError(f"Unknown anatomy: {anatomy!r}.")
    ids = ANATOMY[anatomy]
    if segmentation.label_names != LABELS:
        raise ValueError("Segmentation label catalog does not match the pinned model.")
    mask = np.isin(segmentation.labels, ids)
    boundary = any(np.any(np.take(mask, [0, -1], axis=axis)) for axis in range(3))
    mask.setflags(write=False)
    return VolumeMask(mask, segmentation.grid, ids, tuple(LABELS[i] for i in ids),
                      boundary, dict(segmentation.provenance))
