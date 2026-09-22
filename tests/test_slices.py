import numpy as np
import pytest

from loader import Volume, manifest_fingerprint
from slices import VolumeRegistry, extract_slice, pixel_to_voxel, plane_geometry, volume_descriptor


def fixture_volume():
    z, y, x = np.indices((3, 4, 5))
    direction = (0.8, -0.48, 0.36, 0.6, 0.64, -0.48, 0, 0.6, 0.8)
    return Volume((100*z + 10*y + x + 0.25).astype(np.float32),
                  (0.7, 1.2, 2.5), (12, -23, 45), direction, "private-uid", ("private-file",))


@pytest.mark.parametrize("axis,shape,spacing,count", [
    ("axial", (4, 5), (0.7, 1.2), 3),
    ("coronal", (3, 5), (0.7, 2.5), 4),
    ("sagittal", (3, 4), (1.2, 2.5), 5),
])
def test_all_landmarks_geometry_and_exact_float_transport(axis, shape, spacing, count):
    volume = fixture_volume()
    original = volume.voxels.copy()
    geometry = plane_geometry(volume, axis)
    assert (geometry["height"], geometry["width"]) == shape
    assert geometry["spacing"] == list(spacing)
    assert geometry["count"] == count
    for index in range(count):
        plane = extract_slice(volume, axis, index)
        assert plane.dtype.str == "<f4" and plane.flags.c_contiguous
        decoded = np.frombuffer(plane.tobytes(), dtype="<f4").reshape(shape)
        displayed = decoded[::-1] if geometry["flip_y"] else decoded
        for row, col in np.ndindex(shape):
            x, y, z = pixel_to_voxel(volume, axis, index, col, row)
            assert displayed[row, col] == volume.voxels[z, y, x] == 100*z + 10*y + x + 0.25
    np.testing.assert_array_equal(volume.voxels, original)
    xyz = np.array(pixel_to_voxel(volume, axis, 1, 1, 1))
    matrix = np.array(volume.direction).reshape(3, 3)
    physical = volume.origin + matrix @ (xyz * volume.spacing)
    next_xyz = np.array(pixel_to_voxel(volume, axis, 1, 2, 1))
    np.testing.assert_allclose(volume.origin + matrix @ (next_xyz * volume.spacing) - physical,
                               np.array(geometry["right_lps"]) * spacing[0])
    next_xyz = np.array(pixel_to_voxel(volume, axis, 1, 1, 2))
    np.testing.assert_allclose(volume.origin + matrix @ (next_xyz * volume.spacing) - physical,
                               np.array(geometry["down_lps"]) * spacing[1])


@pytest.mark.parametrize("axis,index", [("bad", 0), ("axial", -1), ("axial", 3),
                                         ("coronal", 4), ("sagittal", 5),
                                         ("axial", 0.5), ("axial", True), ("axial", "0")])
def test_invalid_slice(axis, index):
    with pytest.raises(ValueError):
        extract_slice(fixture_volume(), axis, index)


def test_descriptor_excludes_source_identifiers():
    descriptor = volume_descriptor(fixture_volume(), "token")
    assert "private" not in str(descriptor)
    assert descriptor["dtype"] == "float32" and descriptor["byte_order"] == "little"


def test_registry_count_byte_limit_eviction_does_not_mutate_volume():
    volume = fixture_volume()
    store = VolumeRegistry(max_count=2, max_bytes=volume.voxels.nbytes)
    reserved = store.reserve("one")
    assert store.register("one", volume) == reserved
    assert store.get(reserved) is volume
    second = store.register("two", fixture_volume())
    with pytest.raises(KeyError): store.get(reserved)
    assert volume.voxels[2, 3, 4] == 234.25
    assert store.retained_bytes == volume.voxels.nbytes
    store.reserve("three"); store.reserve("four")
    with pytest.raises(KeyError): store.get(second)
    assert store.retained_bytes == 0
    assert store.reserve("one") != reserved


def test_idle_ttl_refresh_and_restart():
    now = [0]
    store = VolumeRegistry(ttl=10, clock=lambda: now[0])
    token = store.register("source", fixture_volume())
    now[0] = 9
    assert store.get(token)
    now[0] = 18
    assert store.reserve("source") == token
    now[0] = 28
    with pytest.raises(KeyError): store.get(token)
    assert store.reserve("source") != token
    with pytest.raises(KeyError): VolumeRegistry().get(token)


def test_periodic_prune_releases_idle_references():
    now = [0]
    store = VolumeRegistry(ttl=10, clock=lambda: now[0])
    store.register("source", fixture_volume())
    assert store.retained_bytes > 0
    now[0] = 10
    store.prune()
    assert store.retained_bytes == 0


def test_oversized_volume_and_file_change(tmp_path):
    volume = fixture_volume()
    store = VolumeRegistry(max_bytes=1)
    token = store.reserve("large")
    assert store.register("large", volume) is None
    assert store.retained_bytes == 0 and store.reserve("large") == token
    with pytest.raises(KeyError): store.get(token)
    folder = tmp_path / "ct"; folder.mkdir()
    source = folder / "image"; source.write_bytes(b"before")
    first = manifest_fingerprint(tmp_path, "ct")
    token = store.reserve(first)
    source.write_bytes(b"after")
    second = manifest_fingerprint(tmp_path, "ct")
    assert first != second and store.reserve(second) != token
