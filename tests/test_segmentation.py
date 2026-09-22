import os
import sys

import numpy as np
import pytest
import SimpleITK as sitk

from loader import Volume
from meshing import gltf_coordinates, mask_to_mesh
from segmentation import (ANATOMY, GROUPS, LABELS, Grid, Segmentation, grid_image,
                          restore_labels, select_anatomy)
from segmentation_backend import QUALITIES, model_fingerprint, run_worker, segment_volume


def volume(reflected=False):
    direction = np.array([[0.8, -0.48, 0.36], [0.6, 0.64, -0.48], [0, 0.6, 0.8]])
    if reflected:
        direction[:, 0] *= -1
    return Volume(np.zeros((7, 8, 9), dtype=np.float32), (0.7, 1.2, 2.5),
                  (12, -23, 45), tuple(direction.ravel()), "test-series", ("slice.dcm",))


@pytest.mark.parametrize("reflected", [False, True])
def test_independent_physical_landmark_and_nifti_roundtrip(tmp_path, reflected):
    source = volume(reflected)
    source.voxels[4, 3, 2] = 51
    grid = Grid.from_volume(source)
    image = grid_image(source.voxels, grid)
    x = np.array([-0.8, -0.6, 0]) if reflected else np.array([0.8, 0.6, 0])
    expected = np.array([12, -23, 45]) + x*1.4 + np.array([-0.48, 0.64, 0.6])*3.6 + np.array([0.36, -0.48, 0.8])*10
    np.testing.assert_allclose(image.TransformIndexToPhysicalPoint((2, 3, 4)), expected)
    path = tmp_path / "grid.nii"
    sitk.WriteImage(image, str(path))
    # NIfTI sform rows are RAS, independent of SimpleITK's LPS readback.
    import struct
    header = path.read_bytes()[:348]
    affine = np.array(struct.unpack_from("<12f", header, 280)).reshape(3, 4)
    np.testing.assert_allclose(affine @ [2, 3, 4, 1], expected * [-1, -1, 1], atol=1e-5)
    restored = restore_labels(sitk.ReadImage(str(path)), grid)
    np.testing.assert_array_equal(restored, source.voxels)


@pytest.mark.parametrize("changed_shape", [False, True])
def test_restore_uses_affine_not_just_shape(changed_shape):
    source = Volume(np.zeros((6, 6, 6), np.float32), (1, 2, 3), (10, 20, 30),
                    tuple(np.eye(3).ravel()), "", ())
    grid = Grid.from_volume(source)
    image = sitk.GetImageFromArray(np.zeros((8, 8, 8) if changed_shape else grid.shape, np.uint8))
    image.SetSpacing(grid.spacing)
    image.SetOrigin((11, 20, 30))
    image[1, 2, 3] = 51
    result = restore_labels(image, grid)
    assert result[3, 2, 2] == 51
    assert np.count_nonzero(result) == 1


@pytest.mark.parametrize("bad", [0.5, 118, -1, np.nan, np.inf])
def test_invalid_backend_values(bad):
    source = volume()
    source.voxels[0, 0, 0] = bad
    grid = Grid.from_volume(source)
    with pytest.raises(ValueError, match="labels"):
        restore_labels(grid_image(source.voxels, grid), grid)


def test_groups_and_selection_are_exact_and_do_not_mutate_hu():
    source = volume()
    before = source.voxels.copy()
    labels = np.resize(np.arange(118, dtype=np.uint8), source.voxels.shape)
    segmentation = Segmentation(labels, Grid.from_volume(source), dict(LABELS), {})
    assert GROUPS == {"both lungs": (10, 11, 12, 13, 14), "left lung": (10, 11),
                      "right lung": (12, 13, 14), "all ribs": tuple(range(92, 116)),
                      "thoracic vertebrae": tuple(range(32, 44))}
    assert len(LABELS) == 117
    for name, ids in ANATOMY.items():
        mask = select_anatomy(segmentation, name)
        assert set(np.unique(labels[mask.mask])) == set(ids)
        assert mask.grid.series_uid == "test-series"
        assert mask.grid.source_files == ("slice.dcm",)
    np.testing.assert_array_equal(source.voxels, before)
    with pytest.raises(ValueError, match="Unknown anatomy"):
        select_anatomy(segmentation, "heart_chambers")


@pytest.mark.parametrize("reflected", [False, True])
def test_mask_padding_bounds_winding_and_disconnected_components(reflected):
    source = volume(reflected)
    labels = np.zeros(source.voxels.shape, np.uint8)
    labels[0:2, 1:3, 1:3] = 51
    labels[4:6, 5:7, 5:7] = 51
    selected = select_anatomy(Segmentation(labels, Grid.from_volume(source), LABELS, {}), "heart")
    assert selected.touches_boundary
    vertices, faces, normals = mask_to_mesh(selected)
    transform = np.array(source.direction).reshape(3, 3) @ np.diag(source.spacing)
    index = (vertices - source.origin) @ np.linalg.inv(transform).T
    np.testing.assert_allclose(index.min(0), [0.5, 0.5, -0.5], atol=1e-5)
    np.testing.assert_allclose(index.max(0), [6.5, 6.5, 5.5], atol=1e-5)
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    assert np.all(np.einsum("ij,ij->i", cross, normals[faces].mean(1)) > 0)
    np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1, atol=1e-6)
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    assert np.all(counts == 2)
    assert len(vertices) - len(unique) + len(faces) == 4  # two closed components
    converted, _ = gltf_coordinates(vertices, normals)
    np.testing.assert_allclose(converted[:, 0], -vertices[:, 0]/1000, atol=1e-7)


def test_absent_organ():
    source = volume()
    selected = select_anatomy(Segmentation(source.voxels.astype(np.uint8), Grid.from_volume(source), LABELS, {}), "heart")
    assert not selected.mask.any()
    with pytest.raises(ValueError, match="absent"):
        mask_to_mesh(selected)


@pytest.mark.parametrize("step", [1, 2, 3])
def test_padding_closes_every_boundary_at_coarse_steps(step):
    source = volume()
    labels = np.full(source.voxels.shape, 51, np.uint8)
    selected = select_anatomy(Segmentation(labels, Grid.from_volume(source), LABELS, {}), "heart")
    vertices, faces, normals = mask_to_mesh(selected, step)
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    assert np.all(counts == 2)
    assert len(vertices) - len(unique) + len(faces) == 2


def test_model_changes_invalidate_fingerprint(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("DICOM_SEGMENTATION_CACHE", str(tmp_path))
    (tmp_path / "weights").mkdir()
    weights = tmp_path / "weights" / "checkpoint.pth"
    weights.write_bytes(b"first")
    (tmp_path / "manifest-fast.json").write_text(json.dumps({"files": {"checkpoint.pth": "hash"}}))
    initial = model_fingerprint(QUALITIES[1])
    weights.write_bytes(b"replacement")
    assert model_fingerprint(QUALITIES[1]) != initial


def test_worker_manifest_rejects_corruption(tmp_path, monkeypatch):
    import json
    from scripts import segmentation_worker as worker
    pinned = json.loads((worker.Path(__file__).resolve().parents[1] / "models/total-fast.json").read_text())
    (tmp_path / "manifest-fast.json").write_text(json.dumps(pinned))
    monkeypatch.setattr(worker, "expected_files", lambda cache, quality: (list(pinned["files"]), pinned["sources"]))
    with pytest.raises(RuntimeError, match="Missing/corrupt"):
        worker.verify(tmp_path, "fast")
    pinned["files"][next(iter(pinned["files"]))] = "altered"
    (tmp_path / "manifest-fast.json").write_text(json.dumps(pinned))
    with pytest.raises(RuntimeError, match="manifest"):
        worker.verify(tmp_path, "fast")


def test_offline_guard_allows_ipc_but_blocks_remote():
    from scripts.segmentation_worker import offline_network
    offline_network("socket.connect", (None, "/tmp/local.sock"))
    offline_network("socket.connect", (None, ("127.0.0.1", 1234)))
    with pytest.raises(RuntimeError, match="Network access"):
        offline_network("socket.connect", (None, ("example.com", 443)))


def test_missing_setup_is_actionable(tmp_path, monkeypatch):
    monkeypatch.setenv("DICOM_SEGMENTATION_CACHE", str(tmp_path))
    assert model_fingerprint(QUALITIES[1]) == "missing-model"
    with pytest.raises(RuntimeError, match="SEGMENTATION.md"):
        segment_volume(volume())


def test_worker_failure_has_bounded_diagnostics():
    with pytest.raises(RuntimeError) as error:
        run_worker([sys.executable, "-c", "print('x'*20000); raise SystemExit(2)"])
    assert len(str(error.value)) < 12500


def test_worker_cancellation_reaps_process(tmp_path):
    pidfile = tmp_path / "pid"
    def cancel():
        if pidfile.exists():
            raise InterruptedError("cancelled")
    with pytest.raises(InterruptedError):
        run_worker([sys.executable, "-c",
                    "import os,time; from pathlib import Path; "
                    f"Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(30)"], cancel)
    if os.name != "nt":
        with pytest.raises(ProcessLookupError):
            os.kill(int(pidfile.read_text()), 0)
