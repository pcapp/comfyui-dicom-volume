"""Explicit model setup and isolated offline inference. Run with the worker Python."""

import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time

VERSION = "2.18.0"
TASKS = {"full": (291, 292, 293, 294, 295), "fast": (297,)}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def expected_files(cache, quality):
    from totalsegmentator.map_tasks_config import TASK_ID_WEIGHTS_CONFIGS

    trainer = ("nnUNetTrainer_4000epochs_NoMirroring" if quality == "fast"
               else "nnUNetTrainerNoMirroring")
    files = []
    sources = {}
    for task in TASKS[quality]:
        info = TASK_ID_WEIGHTS_CONFIGS[task]
        folder = info["foldername"]
        base = Path(folder) / f"{trainer}__nnUNetPlans__3d_fullres"
        files.extend(str(base / name) for name in (
            "dataset.json", "plans.json", "fold_0/checkpoint_final.pth"))
        sources[str(task)] = ("https://github.com/wasserth/TotalSegmentator/releases/download/"
                              f"{info['version']}/{folder}.zip")
    return files, sources


def verify(cache, quality):
    path = cache / f"manifest-{quality}.json"
    if not path.exists():
        raise RuntimeError("Missing model manifest. Run setup for this quality; see SEGMENTATION.md.")
    manifest = json.loads(path.read_text())
    pinned = json.loads((Path(__file__).resolve().parents[1] / "models" /
                         f"total-{quality}.json").read_text())
    expected, sources = expected_files(cache, quality)
    if (manifest.get("version") != VERSION or manifest.get("task") != "total"
            or manifest.get("quality") != quality or manifest.get("sources") != sources
            or manifest.get("files") != pinned["files"]
            or set(manifest.get("files", {})) != set(expected)):
        raise RuntimeError("Model manifest does not match the pinned backend. Rerun setup.")
    for name, digest in manifest["files"].items():
        path = cache / "weights" / name
        if not path.is_file() or sha256(path) != digest:
            raise RuntimeError(f"Missing/corrupt model file: {name}. Remove its dataset directory and rerun setup.")
    return manifest


def offline_network(event, args):
    # nnU-Net uses local multiprocessing sockets; only external connections are forbidden.
    if event == "socket.connect":
        address = args[1]
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise RuntimeError("Network access is disabled during segmentation. Run explicit setup first.")


# Spawned preprocessing workers inherit this guard as well.
if os.environ.get("DICOM_SEGMENTATION_OFFLINE") == "1":
    sys.addaudithook(offline_network)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "infer", "verify"])
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--quality", choices=TASKS, default="fast")
    parser.add_argument("--device", choices=["auto", "mps", "cuda", "cpu"], default="auto")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if version("TotalSegmentator") != VERSION:
        raise RuntimeError(f"Install TotalSegmentator=={VERSION} in the isolated worker.")
    cache = args.cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["TOTALSEG_HOME_DIR"] = str(cache)
    os.environ["TOTALSEG_WEIGHTS_PATH"] = str(cache / "weights")
    os.environ["nnUNet_compile"] = "false"
    os.environ["MPLCONFIGDIR"] = str(cache / "matplotlib")
    if args.action != "setup":
        os.environ["DICOM_SEGMENTATION_OFFLINE"] = "1"
        sys.addaudithook(offline_network)
    from totalsegmentator.config import setup_totalseg, set_config_key
    setup_totalseg()
    set_config_key("send_usage_stats", False)
    set_config_key("statistics_disclaimer_shown", True)
    from totalsegmentator.map_to_binary import class_map
    catalog = json.loads((Path(__file__).resolve().parents[1] / "anatomy_labels.json").read_text())
    if class_map["total"] != {int(k): v for k, v in catalog.items()}:
        raise RuntimeError("Backend catalog mismatch.")
    if args.action == "setup":
        from totalsegmentator.libs import download_pretrained_weights
        for task in TASKS[args.quality]:
            download_pretrained_weights(task)
        expected, sources = expected_files(cache, args.quality)
        files = {}
        for name in expected:
            path = cache / "weights" / name
            if not path.is_file() or not path.stat().st_size:
                raise RuntimeError(f"Incomplete checkpoint: {name}. Remove its dataset directory and rerun setup.")
            files[name] = sha256(path)
        manifest = dict(version=VERSION, task="total", quality=args.quality, license="Apache-2.0",
                        sources=sources, files=files)
        pinned = json.loads((Path(__file__).resolve().parents[1] / "models" /
                             f"total-{args.quality}.json").read_text())
        if manifest != pinned:
            raise RuntimeError("Downloaded files do not match the pinned checkpoint hashes. "
                               "Remove the affected dataset directory and rerun setup.")
        target = cache / f"manifest-{args.quality}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.replace(target)
    manifest = verify(cache, args.quality)
    if args.action != "infer":
        print(json.dumps(manifest, indent=2))
        return
    if args.input is None or args.output is None:
        parser.error("infer requires --input and --output")
    import torch
    import nibabel as nib
    from totalsegmentator.python_api import totalsegmentator
    available = {"cpu": True, "mps": torch.backends.mps.is_available(),
                 "cuda": torch.cuda.is_available()}
    device = args.device
    if device == "auto":
        device = next(d for d in ("cuda", "mps", "cpu") if available[d])
    if not available[device]:
        raise RuntimeError(f"Requested device {device} is unavailable. Select auto or cpu.")
    start = time.monotonic()
    print(f"TotalSegmentator {VERSION}: total/{args.quality} on {device}", flush=True)
    result = totalsegmentator(args.input, output=None, task="total", ml=True,
                             fast=args.quality == "fast", device="gpu" if device == "cuda" else device,
                             nr_thr_resamp=2, nr_thr_saving=1, quiet=False, statistics=False,
                             skip_saving=True)
    nib.save(result, args.output)
    report = dict(model="TotalSegmentator", version=VERSION, task="total", quality=args.quality,
                  device=device, seconds=time.monotonic() - start, model_manifest=manifest,
                  packages={p: version(p) for p in ("torch", "nnunetv2", "numpy", "nibabel", "SimpleITK")})
    if os.name != "nt":
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["worker_peak_rss_bytes"] = int(peak if sys.platform == "darwin" else peak * 1024)
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
