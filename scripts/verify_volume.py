"""Offline development report and PNGs. Never changes the stored HU volume."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import SimpleITK as sitk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loader import load_volume, read_header


def window_plane(plane, center, width, spacing):
    pixels = np.rint(np.clip((plane.astype(np.float64) - (center - width / 2)) / width,
                            0, 1) * 255).astype(np.uint8)
    # Square display pixels preserve the physical in-plane aspect ratio.
    scale = min(spacing[:2])
    height = max(1, round(plane.shape[0] * spacing[1] / scale))
    width_px = max(1, round(plane.shape[1] * spacing[0] / scale))
    rows = np.minimum((np.arange(height) * scale / spacing[1]).astype(int), plane.shape[0] - 1)
    cols = np.minimum((np.arange(width_px) * scale / spacing[0]).astype(int), plane.shape[1] - 1)
    return pixels[rows[:, None], cols]


def verify(input_root: Path, selection: str, output: Path):
    volume = load_volume(input_root, selection)
    middle = volume.voxels.shape[0] // 2
    reader = sitk.ImageFileReader()
    reader.SetImageIO("GDCMImageIO")
    reader.SetFileName(volume.source_files[middle])
    reader.SetOutputPixelType(sitk.sitkFloat32)
    independent = sitk.GetArrayFromImage(reader.Execute()).reshape(volume.voxels.shape[1:])
    error = float(np.max(np.abs(independent - volume.voxels[middle])))
    if not np.array_equal(independent, volume.voxels[middle]):
        raise ValueError(f"Independent source-plane comparison failed: max error {error} HU.")
    headers = [read_header(path) for path in volume.source_files]
    output.mkdir(parents=True, exist_ok=False)
    images = []
    for index, center, width, label in [
        (0, 40, 400, "first-soft"), (middle, 40, 400, "middle-soft"),
        (len(headers) - 1, 40, 400, "last-soft"), (middle, 400, 1800, "middle-bone"),
    ]:
        filename = label + ".png"
        pixels = window_plane(volume.voxels[index], center, width, volume.spacing)
        sitk.WriteImage(sitk.GetImageFromArray(pixels), str(output / filename))
        position = np.array(volume.origin) + np.array(volume.direction).reshape(3, 3)[:, 2] * index * volume.spacing[2]
        images.append({"file": filename, "stored_z_index": index, "window_center_hu": center,
                       "window_width_hu": width, "plane_origin_lps_mm": position.tolist(),
                       "png_shape_yx": list(pixels.shape)})
    report = {
        "summary": volume.summary(), "series_uid": volume.series_uid,
        "slice_count": len(headers), "shape_zyx": list(volume.voxels.shape),
        "spacing_xyz_mm": volume.spacing, "origin_lps_mm": volume.origin,
        "direction_row_major": volume.direction, "dtype": str(volume.voxels.dtype),
        "hu_range": [float(volume.voxels.min()), float(volume.voxels.max())],
        "header_expectations": {
            "rows": int(headers[0]["0028|0010"]), "columns": int(headers[0]["0028|0011"]),
            "pixel_spacing_yx_mm": headers[0]["0028|0030"],
            "first_position_lps_mm": headers[0]["0020|0032"],
            "last_position_lps_mm": headers[-1]["0020|0032"],
            "orientation_xy": headers[0]["0020|0037"],
            "rescale_slopes": sorted({header.get("0028|1053", "1") for header in headers}),
            "rescale_intercepts": sorted({header.get("0028|1052", "0") for header in headers}),
        },
        "independent_source_comparison": {"stored_z_index": middle,
                                          "file": Path(volume.source_files[middle]).name,
                                          "max_absolute_error_hu": error},
        "images": images, "display": "Stored array axes; no anatomical labels. "
            "Nearest-neighbor display raster at square physical pixels. Linear window mapping.",
        "human_acceptance": "PENDING: record human observations separately.",
    }
    provenance = input_root / selection / "provenance.json"
    if provenance.exists():
        source = json.loads(provenance.read_text())
        report["sample_attribution"] = {key: source[key] for key in ("citation", "license", "policy")}
        if source["series_uid"] != volume.series_uid or source["observed_count"] != len(headers):
            raise ValueError("Loaded series disagrees with downloaded sample provenance.")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(volume.summary())
    print(f"Independent source plane: exact match ({error:g} HU difference). Report: {output / 'report.json'}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--input-root", type=Path, required=True,
                        help="ComfyUI input directory, e.g. /path/to/ComfyUI/input")
    parser.add_argument("--output", type=Path, default=Path("artifacts/sample-verification"))
    args = parser.parse_args()
    verify(args.input_root, args.directory, args.output)


if __name__ == "__main__":
    main()
