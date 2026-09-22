import os
import shutil
import struct

import numpy as np
import pytest
import SimpleITK as sitk

from loader import discover_directories, load_volume, manifest_fingerprint, read_header


def write_series(folder, uid="1.2.826.0.1.3680043.10.543.1", count=3,
                 modality="CT", localizer=False, positions=None, overrides=None):
    folder.mkdir(parents=True, exist_ok=True)
    x = np.array([0.8, 0.6, 0.0])
    y = np.array([-0.48, 0.64, 0.6])
    normal = np.cross(x, y)
    origin = np.array([12.0, -23.0, 45.0])
    stored = np.arange(count * 12, dtype=np.int16).reshape(count, 3, 4)
    paths = []
    for index in range(count):
        image = sitk.GetImageFromArray(stored[index])
        image.SetSpacing((0.7, 1.2))
        position = origin + index * 2.5 * normal if positions is None else positions[index]
        tags = {
            "0008|0016": "1.2.840.10008.5.1.4.1.1.2",
            "0008|0018": f"{uid}.{index + 1}",
            "0008|0060": modality,
            "0008|0008": "ORIGINAL\\PRIMARY\\LOCALIZER" if localizer else "ORIGINAL\\PRIMARY\\AXIAL",
            "0020|000d": "1.2.826.0.1.3680043.10.543.100",
            "0020|000e": uid,
            "0020|0013": str(index + 1),
            "0020|0032": "\\".join(str(v) for v in position),
            "0020|0037": "\\".join(str(v) for v in np.concatenate((x, y))),
            "0028|0030": "1.2\\0.7",
            "0028|1052": "0",
            "0028|1053": "1",
            "0028|1054": "HU",
        }
        tags.update((overrides or {}).get(index, {}))
        for key, value in tags.items():
            image.SetMetaData(key, value)
        path = folder / f"{uid}-slice-{count-index:03}.dcm"
        writer = sitk.ImageFileWriter()
        writer.KeepOriginalImageUIDOn()
        writer.SetFileName(str(path))
        writer.Execute(image)
        paths.append(path)
    return stored, paths, origin, np.column_stack((x, y, normal))


def replace_ds(path, group, element, value):
    """Patch a fixture's implicit-VR DS without changing stored pixel bytes."""
    data = path.read_bytes()
    assert b"1.2.840.10008.1.2\x00" in data
    tag = struct.pack("<HH", group, element)
    assert data.count(tag) == 1
    offset = data.index(tag)
    old_length = struct.unpack_from("<I", data, offset + 4)[0]
    encoded = value.encode("ascii")
    encoded += b" " * (len(encoded) % 2)
    path.write_bytes(data[:offset + 4] + struct.pack("<I", len(encoded))
                     + encoded + data[offset + 8 + old_length:])


def test_hu_order_geometry_and_extensionless_discovery(tmp_path):
    stored, paths, origin, direction = write_series(tmp_path / "ct")
    for path in paths:
        replace_ds(path, 0x0028, 0x1052, "-1024")
        replace_ds(path, 0x0028, 0x1053, "0.5")
        header = read_header(path)
        assert float(header["0028|1052"]) == -1024
        assert float(header["0028|1053"]) == 0.5
        # Verify actual stored bytes, independently of GDCM rescale behavior.
        data = path.read_bytes()
        pixel_tag = struct.pack("<HH", 0x7FE0, 0x0010)
        offset = data.index(pixel_tag)
        pixels = np.frombuffer(data[offset + 8:], dtype="<i2").reshape(3, 4)
        np.testing.assert_array_equal(pixels, stored[paths.index(path)])
    paths[1].rename(paths[1].with_suffix(""))
    assert discover_directories(tmp_path) == ["ct"]
    volume = load_volume(tmp_path, "ct")
    assert volume.voxels.dtype == np.float32
    np.testing.assert_array_equal(volume.voxels, stored * 0.5 - 1024)
    np.testing.assert_allclose(volume.spacing, [0.7, 1.2, 2.5])
    np.testing.assert_allclose(volume.origin, origin)
    np.testing.assert_allclose(np.array(volume.direction).reshape(3, 3), direction, atol=1e-12)
    physical = np.array(volume.origin) + np.array(volume.direction).reshape(3, 3) @ (
        np.array([3, 2, 1]) * volume.spacing)
    np.testing.assert_allclose(physical, origin + direction[:, 0] * 2.1
                               + direction[:, 1] * 2.4 + direction[:, 2] * 2.5)
    assert "float32" in volume.summary()


def test_per_slice_rescale(tmp_path):
    stored, paths, _, _ = write_series(tmp_path / "ct")
    for index, path in enumerate(paths):
        replace_ds(path, 0x0028, 0x1052, str(-1000 - index))
        replace_ds(path, 0x0028, 0x1053, str(0.5 + index))
    volume = load_volume(tmp_path, "ct")
    for index in range(3):
        np.testing.assert_array_equal(volume.voxels[index], stored[index] * (0.5 + index) - 1000 - index)


def test_series_selection(tmp_path):
    folder = tmp_path / "mixed"
    write_series(folder, uid="1.2.4", count=4)
    write_series(folder, uid="1.2.3", count=4)
    write_series(folder, uid="1.2.2", count=3)
    write_series(folder, uid="1.2.1", count=6, modality="MR")
    write_series(folder, uid="1.2.0", count=7, localizer=True)
    volume = load_volume(tmp_path, "mixed")
    assert volume.series_uid == "1.2.3"
    assert volume.voxels.shape == (4, 3, 4)


@pytest.mark.parametrize("kind", ["empty", "junk", "localizer", "mr", "single"])
def test_no_eligible_ct(tmp_path, kind):
    folder = tmp_path / "ct"
    folder.mkdir()
    if kind == "junk":
        (folder / "invalid.dcm").write_text("not DICOM")
    elif kind in ("localizer", "mr", "single"):
        write_series(folder, localizer=kind == "localizer", modality="MR" if kind == "mr" else "CT",
                     count=1 if kind == "single" else 3)
    with pytest.raises(ValueError, match="No eligible CT"):
        load_volume(tmp_path, "ct")


@pytest.mark.parametrize("selection", ["../escape", "/tmp", "ct/../../escape", ""])
def test_untrusted_selection(tmp_path, selection):
    with pytest.raises(ValueError, match="relative"):
        load_volume(tmp_path, selection)


def test_symlink_escape(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    _, paths, _, _ = write_series(tmp_path / "outside")
    (root / "escape").symlink_to(tmp_path / "outside", target_is_directory=True)
    with pytest.raises(ValueError, match="inside"):
        load_volume(root, "escape")
    folder = root / "ct"
    folder.mkdir()
    (folder / "slice").symlink_to(paths[0])
    with pytest.raises(ValueError, match="escapes"):
        load_volume(root, "ct")
    assert discover_directories(root) == []


@pytest.mark.parametrize("kind", ["duplicate", "gap", "shear", "orientation", "spacing"])
def test_incompatible_geometry(tmp_path, kind):
    positions = np.array([[0., 0., 0.], [0., 0., 2.5], [0., 0., 5.]])
    overrides = {index: {"0020|0037": "1\\0\\0\\0\\1\\0"} for index in range(3)}
    if kind == "duplicate":
        positions[2] = positions[1]
    elif kind == "gap":
        positions[2, 2] = 7.5
    elif kind == "shear":
        positions[:, 0] = [0, 0.5, 1]
    elif kind == "orientation":
        overrides[2]["0020|0037"] = "0\\1\\0\\1\\0\\0"
    write_series(tmp_path / "ct", positions=positions, overrides=overrides)
    if kind == "spacing":
        path = sorted((tmp_path / "ct").iterdir())[0]
        replace_ds(path, 0x0028, 0x0030, "1.3\\0.7")
    with pytest.raises(ValueError, match="positions|orientations|spacing"):
        load_volume(tmp_path, "ct")


def test_manifest_add_replace_remove(tmp_path):
    _, paths, _, _ = write_series(tmp_path / "ct")
    original = manifest_fingerprint(tmp_path, "ct")
    assert manifest_fingerprint(tmp_path, "ct") == original
    stat = paths[0].stat()
    replacement = tmp_path / "replacement"
    shutil.copyfile(paths[0], replacement)
    os.utime(replacement, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    replacement.replace(paths[0])
    replaced = manifest_fingerprint(tmp_path, "ct")
    assert replaced != original
    extra = tmp_path / "ct" / "new-file"
    extra.write_text("new")
    assert manifest_fingerprint(tmp_path, "ct") != replaced
    extra.unlink()
    assert manifest_fingerprint(tmp_path, "ct") == replaced
    paths[1].unlink()
    assert manifest_fingerprint(tmp_path, "ct") != replaced
