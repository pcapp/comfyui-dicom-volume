import numpy as np
import SimpleITK as sitk

from scripts.verify_volume import verify, window_plane
from tests.test_loader import write_series


def test_windows_preserve_volume_and_physical_aspect():
    plane = np.array([[-200, 0, 40, 240], [500, 1000, -1024, 3000]], dtype=np.float32)
    original = plane.copy()
    pixels = window_plane(plane, 40, 400, (0.5, 1, 2))
    assert pixels.shape == (4, 4)
    assert pixels[0, 0] == 0
    assert pixels[0, 2] == 128
    assert pixels[0, 3] == 255
    np.testing.assert_array_equal(plane, original)


def test_report_independent_plane_and_pngs(tmp_path):
    write_series(tmp_path / "ct")
    output = tmp_path / "report"
    report = verify(tmp_path, "ct", output)
    assert report["independent_source_comparison"]["max_absolute_error_hu"] == 0
    assert report["shape_zyx"] == [3, 3, 4]
    assert report["human_acceptance"].startswith("PENDING")
    assert len(report["images"]) == 4
    for image in report["images"]:
        pixels = sitk.GetArrayFromImage(sitk.ReadImage(str(output / image["file"])))
        assert list(pixels.shape) == image["png_shape_yx"]
