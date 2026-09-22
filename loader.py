"""Conventional CT loading, independent of ComfyUI. Physical coordinates are LPS mm."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import SimpleITK as sitk


@dataclass
class Volume:
    voxels: np.ndarray  # float32 HU, indexed [z, y, x]
    spacing: tuple[float, float, float]  # x, y, z in mm
    origin: tuple[float, float, float]  # DICOM LPS mm
    direction: tuple[float, ...]  # row-major 3x3, columns are x/y/z directions
    series_uid: str
    source_files: tuple[str, ...]  # GDCM spatial order

    def summary(self) -> str:
        return (
            f"Series {self.series_uid}; slices={len(self.source_files)}; "
            f"shape(z,y,x)={self.voxels.shape}; spacing(x,y,z)={self.spacing} mm; "
            f"dtype={self.voxels.dtype}; "
            f"HU=[{float(self.voxels.min()):g}, {float(self.voxels.max()):g}]"
        )


def selected_directory(input_root: str | Path, selection: str) -> Path:
    root = Path(input_root).resolve(strict=True)
    relative = Path(selection)
    if not selection or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Select a relative DICOM directory inside ComfyUI's input root.")
    directory = (root / relative).resolve(strict=True)
    if not directory.is_relative_to(root) or not directory.is_dir():
        raise ValueError("The selected directory must stay inside ComfyUI's input root.")
    return directory


def directory_files(input_root: str | Path, selection: str) -> tuple[Path, list[Path]]:
    root = Path(input_root).resolve(strict=True)
    directory = selected_directory(root, selection)
    files = []
    for path in sorted(directory.iterdir()):
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError("A directory entry escapes the input root. Remove the external symlink.")
        if resolved.is_file():
            files.append(path)
    return directory, files


def manifest_fingerprint(input_root: str | Path, selection: str) -> str:
    directory, files = directory_files(input_root, selection)
    manifest = []
    for path in files:
        stat = path.stat()
        manifest.append((path.name, str(path.resolve()), stat.st_size,
                         stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino))
    return hashlib.sha256(json.dumps([str(directory), manifest]).encode()).hexdigest()


def discover_directories(input_root: str | Path) -> list[str]:
    root = Path(input_root).resolve()
    if not root.is_dir():
        return []
    options = []
    for directory, children, _ in os.walk(root, followlinks=False):
        children[:] = sorted(name for name in children
                             if not (Path(directory) / name).is_symlink())
        relative = Path(directory).relative_to(root).as_posix()
        try:
            checked, files = directory_files(root, relative)
            # GDCM reads headers, including extensionless files, but not pixel data.
            if files and sitk.ImageSeriesReader.GetGDCMSeriesIDs(str(checked)):
                options.append(relative)
        except (OSError, ValueError, RuntimeError):
            continue
    return sorted(options)


def read_header(path: str | Path) -> dict[str, str]:
    reader = sitk.ImageFileReader()
    reader.SetImageIO("GDCMImageIO")
    reader.SetFileName(str(path))
    reader.ReadImageInformation()
    return {key: reader.GetMetaData(key).strip() for key in reader.GetMetaDataKeys()}


def _numbers(header: dict[str, str], key: str, count: int) -> np.ndarray:
    try:
        values = np.array([float(value) for value in header[key].split("\\")])
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Missing or invalid DICOM geometry tag {key}; export a conventional CT series.") from exc
    if values.shape != (count,) or not np.isfinite(values).all():
        raise ValueError(f"Invalid DICOM geometry tag {key}; export a conventional CT series.")
    return values


def _validate_geometry(headers: list[dict[str, str]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    first = headers[0]
    orientation = _numbers(first, "0020|0037", 6)
    x, y = orientation[:3], orientation[3:]
    if not np.allclose([np.linalg.norm(x), np.linalg.norm(y), np.dot(x, y)],
                       [1, 1, 0], atol=1e-4, rtol=0):
        raise ValueError("Invalid slice orientation; export orthogonal in-plane CT axes.")
    pixel_spacing = _numbers(first, "0028|0030", 2)
    if np.any(pixel_spacing <= 0):
        raise ValueError("Pixel spacing must be positive.")
    positions = []
    for header in headers:
        if header.get("0008|0016") != "1.2.840.10008.5.1.4.1.1.2":
            raise ValueError("Only conventional CT Image Storage is supported; export single-frame CT slices.")
        if header.get("0028|0008", "1") != "1":
            raise ValueError("Enhanced/multiframe CT is not supported; export single-frame CT slices.")
        if header.get("0028|1054", "HU").upper() != "HU":
            raise ValueError("CT rescale units are not HU; export a Hounsfield-unit reconstruction.")
        if (header.get("0028|0010"), header.get("0028|0011")) != (
                first.get("0028|0010"), first.get("0028|0011")):
            raise ValueError("Inconsistent slice dimensions; export one reconstruction grid.")
        if not np.allclose(_numbers(header, "0020|0037", 6), orientation, atol=1e-4, rtol=0):
            raise ValueError("Inconsistent slice orientations; export one regular CT stack.")
        if not np.allclose(_numbers(header, "0028|0030", 2), pixel_spacing, atol=1e-5, rtol=1e-5):
            raise ValueError("Inconsistent pixel spacing; export one reconstruction grid.")
        positions.append(_numbers(header, "0020|0032", 3))
    positions = np.array(positions)
    normal = np.cross(x, y)
    steps = np.diff(positions, axis=0)
    distances = steps @ normal
    if np.any(distances <= 1e-5):
        raise ValueError("Duplicate or unordered slice positions; remove duplicates and export one CT stack.")
    dz = float(np.mean(distances))
    # Allow DICOM decimal rounding, but never hide missing slices or gantry shear.
    if not np.allclose(steps, normal * dz, atol=max(0.001, dz * 0.001), rtol=0):
        raise ValueError("Irregular slice positions or gantry tilt/shear cannot be represented by this grid; "
                         "export a regular reconstruction (this loader does not resample).")
    spacing = np.array([pixel_spacing[1], pixel_spacing[0], dz])
    direction = np.column_stack((x, y, normal))
    return positions, spacing, direction


def load_volume(input_root: str | Path, selection: str) -> Volume:
    directory, allowed_files = directory_files(input_root, selection)
    before = manifest_fingerprint(input_root, selection)
    allowed = {path.resolve() for path in allowed_files}
    candidates = []
    for uid in sitk.ImageSeriesReader.GetGDCMSeriesIDs(str(directory)) or ():
        files = tuple(sitk.ImageSeriesReader.GetGDCMSeriesFileNames(str(directory), uid))
        if any(Path(path).resolve(strict=True) not in allowed for path in files):
            raise ValueError("A selected DICOM file is outside the validated input directory.")
        headers = [read_header(path) for path in files]
        eligible = [(path, header) for path, header in zip(files, headers)
                    if header.get("0008|0060") == "CT"
                    and not {"LOCALIZER", "SCOUT"}.intersection(
                        header.get("0008|0008", "").upper().split("\\"))]
        if len(eligible) >= 2:
            candidates.append((uid, tuple(path for path, _ in eligible),
                               [header for _, header in eligible]))
    if not candidates:
        raise ValueError("No eligible CT volume found. Select a complete single-frame CT series "
                         "with at least two slices, excluding scouts/localizers.")
    uid, files, headers = min(candidates, key=lambda candidate: (-len(candidate[1]), candidate[0]))
    positions, spacing, direction = _validate_geometry(headers)
    reader = sitk.ImageSeriesReader()
    reader.SetImageIO("GDCMImageIO")
    reader.SetFileNames(files)
    # GDCM applies each slice's rescale slope/intercept. Float output preserves fractions.
    reader.SetOutputPixelType(sitk.sitkFloat32)
    image = reader.Execute()
    if (image.GetDimension() != 3 or image.GetNumberOfComponentsPerPixel() != 1
            or image.GetSize()[2] != len(files)):
        raise ValueError("Expected one scalar 2D CT image per file; enhanced/multiframe CT is unsupported.")
    actual_direction = np.array(image.GetDirection()).reshape(3, 3)
    actual_positions = (np.array(image.GetOrigin()) + np.arange(len(files))[:, None]
                        * actual_direction[:, 2] * image.GetSpacing()[2])
    if (not np.allclose(image.GetSpacing(), spacing, atol=0.001, rtol=0.001)
            or not np.allclose(actual_direction, direction, atol=1e-4, rtol=0)
            or not np.allclose(actual_positions, positions, atol=0.001, rtol=0)):
        raise ValueError("Decoded geometry disagrees with DICOM headers; export a regular CT reconstruction.")
    if manifest_fingerprint(input_root, selection) != before:
        raise ValueError("Input files changed during loading; finish copying the series and queue again.")
    voxels = sitk.GetArrayFromImage(image)
    return Volume(voxels, image.GetSpacing(), image.GetOrigin(), image.GetDirection(), uid, files)
