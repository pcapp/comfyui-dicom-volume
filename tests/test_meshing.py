import numpy as np
import pytest

from loader import Volume
from meshing import gltf_coordinates, volume_to_mesh


def sphere(spacing=(1, 1, 1), origin=(0, 0, 0), direction=None):
    z, y, x = np.indices((25, 25, 25))
    hu = 1000 - 100 * np.sqrt((x - 12)**2 + (y - 12)**2 + (z - 12)**2)
    return Volume(hu.astype(np.float32), spacing, origin,
                  tuple((np.eye(3) if direction is None else direction).ravel()), "", ())


@pytest.mark.parametrize("step", [1, 2, 3])
@pytest.mark.parametrize("reflected", [False, True])
def test_physical_geometry_winding_and_closed_topology(step, reflected):
    direction = np.array([[0.8, -0.48, 0.36], [0.6, 0.64, -0.48], [0, 0.6, 0.8]])
    if reflected:
        direction[:, 0] *= -1
    spacing = np.array([0.7, 1.2, 2.5])
    origin = np.array([12, -23, 45])
    volume = sphere(spacing, origin, direction)
    vertices, faces, normals = volume_to_mesh(volume, 200, step)
    center = origin + direction @ (np.array([12, 12, 12]) * spacing)
    extent = 8 * np.linalg.norm(direction * spacing, axis=1)
    tolerance = max(spacing) * step
    np.testing.assert_allclose(vertices.min(0), center - extent, atol=tolerance)
    np.testing.assert_allclose(vertices.max(0), center + extent, atol=tolerance)
    triangles = vertices[faces].astype(float)
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    assert np.all(np.einsum("ij,ij->i", cross, triangles.mean(1) - center) > 0)
    assert np.all(np.einsum("ij,ij->i", cross, normals[faces].mean(1)) > 0)
    assert np.all(np.einsum("ij,ij->i", normals, vertices - center) > 0)
    np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1, atol=1e-6)
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    assert np.all(counts == 2)
    assert len(vertices) - len(unique) + len(faces) == 2


def test_threshold_and_axis_spacing_origin():
    volume = sphere((0.5, 2, 3), (10, -20, 30))
    before = volume.voxels.copy()
    for threshold, radius in [(200, 8), (400, 6)]:
        vertices, _, _ = volume_to_mesh(volume, threshold, 1)
        np.testing.assert_allclose(vertices.min(0), np.array(volume.origin) + (12-radius)*np.array(volume.spacing))
        np.testing.assert_allclose(vertices.max(0), np.array(volume.origin) + (12+radius)*np.array(volume.spacing))
    np.testing.assert_array_equal(volume.voxels, before)


def test_gltf_units_orientation_and_origin():
    vertices, normals = gltf_coordinates(np.array([[100, 200, 300]], dtype=np.float32),
                                        np.array([[1, 0, 0]], dtype=np.float32))
    np.testing.assert_allclose(vertices, [[-0.1, 0.3, 0.2]])
    np.testing.assert_array_equal(normals, [[-1, 0, 0]])
    assert vertices.dtype == np.float32


def test_normals_follow_inverse_transpose_of_anisotropic_affine():
    identity = sphere()
    anisotropic = sphere((0.5, 2, 3), (10, -20, 30))
    _, faces, base_normals = volume_to_mesh(identity)
    _, transformed_faces, normals = volume_to_mesh(anisotropic)
    expected = base_normals / anisotropic.spacing
    expected /= np.linalg.norm(expected, axis=1, keepdims=True)
    np.testing.assert_allclose(normals, expected, atol=1e-6)
    np.testing.assert_array_equal(faces, transformed_faces)


@pytest.mark.parametrize("step", [0, -1, 1.5, True, 25])
def test_invalid_steps(step):
    with pytest.raises(ValueError, match="step_size"):
        volume_to_mesh(sphere(), step_size=step)


@pytest.mark.parametrize("threshold", [float("nan"), float("inf"), "200", True])
def test_invalid_threshold(threshold):
    with pytest.raises(ValueError, match="threshold_hu"):
        volume_to_mesh(sphere(), threshold)


@pytest.mark.parametrize("kind", ["constant", "outside", "maximum", "missed", "small", "nan"])
def test_no_surface_and_constraints(kind):
    volume = sphere()
    threshold, step = 200, 2
    if kind == "constant":
        volume.voxels[:] = 0
    elif kind == "outside":
        threshold = 2000
    elif kind == "maximum":
        threshold = 1000
    elif kind == "missed":
        volume.voxels[:] = 0
        volume.voxels[1, 1, 1] = 1000
    elif kind == "small":
        volume.voxels = volume.voxels[:1]
    else:
        volume.voxels[0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="No surface|two voxels|finite"):
        volume_to_mesh(volume, threshold, step)
