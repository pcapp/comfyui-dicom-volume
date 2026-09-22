"""Run real segmentation and produce attributed geometry/overlay evidence."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import SimpleITK as sitk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from loader import load_volume
from segmentation import grid_image, select_anatomy
from segmentation_backend import QUALITIES, segment_volume
from meshing import gltf_coordinates, mask_to_mesh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--directory", default="tcia-med-lymph-073")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quality", choices=["fast", "full"], default="fast")
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    volume = load_volume(args.input_root, args.directory)
    before = volume.voxels.copy()
    segmentation = segment_volume(volume, QUALITIES[args.quality == "fast"], args.device)
    np.testing.assert_array_equal(before, volume.voxels)
    sitk.WriteImage(grid_image(segmentation.labels, segmentation.grid), str(args.output / "labels.nii.gz"))
    report = dict(provenance=segmentation.provenance, shape=list(segmentation.labels.shape),
                  spacing=volume.spacing, origin=volume.origin, direction=volume.direction,
                  labels={segmentation.label_names[int(i)]: int(n) for i, n in zip(
                      *np.unique(segmentation.labels, return_counts=True)) if i}, organs={})
    for anatomy in ("heart", "both lungs", "aorta"):
        mask = select_anatomy(segmentation, anatomy)
        vertices, faces, normals = mask_to_mesh(mask)
        vertices, normals = gltf_coordinates(vertices, normals)
        report["organs"][anatomy] = dict(voxels=int(mask.mask.sum()), vertices=len(vertices),
            triangles=len(faces), touches_boundary=mask.touches_boundary,
            bounds_m=[vertices.min(0).tolist(), vertices.max(0).tolist()])
    # Portable overlay PNGs without adding a plotting dependency to the host.
    colors = {51: (255, 80, 80), 52: (255, 220, 50),
              10: (60, 200, 255), 11: (60, 200, 255), 12: (60, 200, 255),
              13: (60, 200, 255), 14: (60, 200, 255)}
    heart = np.argwhere(segmentation.labels == 51)
    center = np.median(heart, axis=0).astype(int)
    for axis, name in enumerate(("axial", "coronal", "sagittal")):
        plane = np.take(volume.voxels, center[axis], axis=axis)
        labels = np.take(segmentation.labels, center[axis], axis=axis)
        gray = np.clip((plane + 160) / 400 * 255, 0, 255)
        rgb = np.repeat(gray[..., None], 3, axis=2)
        for label, color in colors.items():
            rgb[labels == label] = rgb[labels == label] * 0.55 + np.array(color) * 0.45
        image = sitk.GetImageFromArray(rgb.astype(np.uint8), isVector=True)
        spacing = np.delete(np.array(volume.spacing)[::-1], axis)[::-1]
        image.SetSpacing(tuple(spacing))
        # Render square display pixels while preserving physical aspect.
        size = np.maximum(1, np.rint(np.array(image.GetSize()) * spacing / min(spacing)).astype(int))
        image = sitk.Resample(image, [int(i) for i in size], sitk.Transform(), sitk.sitkNearestNeighbor,
                              image.GetOrigin(), (min(spacing), min(spacing)), image.GetDirection())
        sitk.WriteImage(image, str(args.output / f"{name}.png"))
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "ATTRIBUTION.md").write_text((ROOT / "SAMPLE_DATA.md").read_text() +
        "\nDerived using TotalSegmentator 2.18.0 standard total, Apache-2.0.\n"
        "Overlays: heart red, lungs cyan, aorta yellow. Stored-axis views.\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
