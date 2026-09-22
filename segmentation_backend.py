"""Optional isolated TotalSegmentator worker and cancellable host adapter."""

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile

import SimpleITK as sitk

try:
    from .segmentation import Grid, LABELS, Segmentation, grid_image, restore_labels
except ImportError:
    from segmentation import Grid, LABELS, Segmentation, grid_image, restore_labels

VERSION = "2.18.0"
QUALITIES = ["full (1.5 mm)", "fast (3 mm)"]
ROOT = Path(__file__).resolve().parent
SETUP_HELP = "Run the setup commands in SEGMENTATION.md for the selected quality."


def model_cache():
    return Path(os.environ.get("DICOM_SEGMENTATION_CACHE", ROOT / "artifacts" / "totalsegmentator"))


def worker_python():
    return Path(os.environ.get("DICOM_SEGMENTATION_PYTHON", ROOT / ".venv-segmentation" /
                               ("Scripts/python.exe" if os.name == "nt" else "bin/python")))


def quality_key(quality):
    if quality not in QUALITIES:
        raise ValueError(f"Unknown segmentation quality: {quality!r}.")
    return "fast" if quality == QUALITIES[1] else "full"


def model_fingerprint(quality):
    """Include all model file identities so changed checkpoints invalidate graph cache."""
    path = model_cache() / f"manifest-{quality_key(quality)}.json"
    if not path.is_file():
        return "missing-model"
    try:
        manifest = json.loads(path.read_text())
        records = []
        for relative in manifest["files"]:
            stat = (model_cache() / "weights" / relative).stat()
            records.append((relative, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
        payload = [path.read_text(), records, str(worker_python()),
                   (ROOT / "scripts" / "segmentation_worker.py").read_text(),
                   (ROOT / "models" / f"total-{quality_key(quality)}.json").read_text(),
                   (ROOT / "anatomy_labels.json").read_text(), VERSION]
        return hashlib.sha256(json.dumps(payload).encode()).hexdigest()
    except (OSError, ValueError, KeyError):
        return "invalid-model"


def run_worker(command, check_cancel=lambda: None):
    """Keep diagnostics bounded in memory; terminate the process tree on cancellation."""
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=os.name != "nt")
        try:
            while True:
                check_cancel()
                try:
                    code = process.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if process.poll() is None:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if os.name != "nt":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait()
        if code:
            log.seek(0, os.SEEK_END)
            log.seek(max(0, log.tell() - 12000))
            raise RuntimeError("TotalSegmentator worker failed. " + SETUP_HELP + "\n" +
                               log.read().decode(errors="replace"))


def segment_volume(volume, quality=QUALITIES[1], device="auto", check_cancel=lambda: None):
    mode = quality_key(quality)
    if device not in ("auto", "mps", "cuda", "cpu"):
        raise ValueError(f"Unsupported segmentation device: {device!r}.")
    if not worker_python().is_file() or model_fingerprint(quality) in ("missing-model", "invalid-model"):
        raise RuntimeError("TotalSegmentator dependencies or weights are missing. " + SETUP_HELP)
    grid = Grid.from_volume(volume)
    with tempfile.TemporaryDirectory(prefix="dicom-segmentation-") as directory:
        directory = Path(directory)
        source, target = directory / "input.nii.gz", directory / "labels.nii.gz"
        sitk.WriteImage(grid_image(volume.voxels, grid), str(source))
        run_worker([str(worker_python()), str(ROOT / "scripts" / "segmentation_worker.py"),
                    "infer", "--cache", str(model_cache()), "--quality", mode,
                    "--device", device, "--input", str(source), "--output", str(target)], check_cancel)
        check_cancel()
        labels = restore_labels(sitk.ReadImage(str(target)), grid)
        provenance = json.loads(target.with_suffix(".json").read_text())
        return Segmentation(labels, grid, dict(LABELS), provenance)
