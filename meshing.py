"""Isosurfaces in physical DICOM LPS millimetres, independent of ComfyUI."""

from numbers import Integral, Real

import numpy as np
from skimage.measure import marching_cubes


def volume_to_mesh(volume, threshold_hu=200.0, step_size=2):
    if isinstance(threshold_hu, bool) or not isinstance(threshold_hu, Real) or not np.isfinite(threshold_hu):
        raise ValueError("threshold_hu must be a finite HU number.")
    if isinstance(step_size, bool) or not isinstance(step_size, Integral) or step_size < 1:
        raise ValueError("step_size must be an integer of at least 1.")
    voxels = volume.voxels
    if voxels.ndim != 3 or min(voxels.shape) < 2:
        raise ValueError("Meshing needs at least two voxels along every axis.")
    if step_size >= min(voxels.shape):
        raise ValueError("Reduce step_size below the smallest volume dimension.")
    if not np.isfinite(voxels).all():
        raise ValueError("Volume HU values must be finite. Check the source data.")
    low, high = float(voxels.min()), float(voxels.max())
    if not low <= threshold_hu <= high or low == high:
        raise ValueError(f"No surface: choose a threshold within HU range [{low:g}, {high:g}].")
    try:
        # ascent gives right-hand outward winding around high-HU regions in z,y,x.
        vertices, faces, normals, _ = marching_cubes(
            voxels, level=threshold_hu, step_size=step_size,
            gradient_direction="ascent", allow_degenerate=False,
        )
    except RuntimeError as error:
        raise ValueError("No surface: change threshold_hu or reduce step_size.") from error
    if not len(faces):
        raise ValueError("No surface: change threshold_hu or reduce step_size.")
    direction = np.asarray(volume.direction).reshape(3, 3)
    transform = direction @ np.diag(volume.spacing) @ np.eye(3)[::-1]
    vertices = vertices @ transform.T + volume.origin
    if np.linalg.det(transform) < 0:
        faces = faces[:, ::-1]
    # Gradient normals use the inverse transpose, not the vertex affine.
    # Retain valid normals even for vertices left unused by degenerate-face removal.
    normals = normals @ np.linalg.inv(transform)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    np.divide(normals, lengths, out=normals, where=lengths > 0)
    return (np.ascontiguousarray(vertices, dtype=np.float32),
            np.ascontiguousarray(faces, dtype=np.int64),
            np.ascontiguousarray(normals, dtype=np.float32))


def gltf_coordinates(vertices, normals):
    """LPS mm -> right-handed glTF metres: (X,Y,Z)=(-L,S,P)/1000."""
    rotation = np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]], dtype=np.float32)
    return (np.ascontiguousarray((vertices @ rotation.T) * np.float32(0.001)),
            np.ascontiguousarray(normals @ rotation.T))


def mask_to_mesh(volume_mask, step_size=1):
    """Pad binary anatomy to close the surface, retaining the source coordinates."""
    from types import SimpleNamespace

    if isinstance(step_size, bool) or not isinstance(step_size, Integral) or step_size < 1:
        raise ValueError("step_size must be an integer of at least 1.")
    mask = volume_mask.mask
    if mask.dtype != np.bool_ or mask.ndim != 3 or tuple(mask.shape) != volume_mask.grid.shape:
        raise ValueError("Expected a boolean mask on the original volume grid.")
    if not mask.any():
        raise ValueError("No surface: selected anatomy is absent from this scan.")
    grid = volume_mask.grid
    direction = np.asarray(grid.direction).reshape(3, 3)
    if step_size > min(mask.shape):
        raise ValueError("Reduce step_size to the smallest mask dimension or less.")
    # A full sampling stride of zeros closes all six boundaries even at coarse steps.
    padded = SimpleNamespace(voxels=np.pad(mask.astype(np.float32), step_size),
                             spacing=grid.spacing, direction=grid.direction,
                             origin=np.asarray(grid.origin) - direction @ (np.asarray(grid.spacing) * step_size))
    return volume_to_mesh(padded, threshold_hu=0.5, step_size=step_size)
