# Organ Segmentation

Use `example_workflows/dicom_organs.json` in ComfyUI. It connects one
**Segment CT Anatomy** node to separate heart, both-lungs and aorta selectors,
then **Mask to Mesh** and core **Save 3D Model** nodes. Each selector has a native
single dropdown with 117 individual labels and five explicit groups. Add selector
branches for more exports. Changing a selector reuses ComfyUI's cached inference.
No custom frontend or multi-select is needed.

## Optional Setup

First complete the [base installation and sample download](README.md#setup).
Open another terminal and `cd` into the extension checkout before running these
commands; the terminal running ComfyUI remains in the host checkout.

The loader and HU meshing need no segmentation packages. TotalSegmentator runs
in an isolated Python 3.12 worker, leaving the host interpreter and packages alone.
From this extension directory, with uv installed:

```sh
uv venv --python 3.12 .venv-segmentation
uv pip install --python .venv-segmentation/bin/python -r requirements-segmentation.txt
.venv-segmentation/bin/python scripts/segmentation_worker.py setup --cache artifacts/totalsegmentator --quality fast
# Optional full-quality model, about 1.17 GB compressed across five checkpoints:
.venv-segmentation/bin/python scripts/segmentation_worker.py setup --cache artifacts/totalsegmentator --quality full
```

Fast downloads about 135 MB compressed. Setup displays upstream byte progress,
checks expected trainer/plans/dataset files and verifies their pinned SHA-256
hashes before accepting the model. Only the requested standard `total` checkpoints
are downloaded. Models live under ignored `artifacts/totalsegmentator`, outside
tracked files. `models/total-{fast,full}.json` records identities, sources, hashes
and license. These hashes were measured from the official release assets; they
are integrity pins, not upstream-signed attestations.

For the exact tested macOS arm64 environment, install
`requirements-segmentation-macos.lock.txt` instead of the shorter requirements
file. The snapshot includes all resolved worker dependencies. Other platforms
use the shorter core pins and resolve their platform-specific dependencies.

On Windows use `.venv-segmentation/Scripts/python.exe`. For an externally managed
worker/cache, set absolute `DICOM_SEGMENTATION_PYTHON` and
`DICOM_SEGMENTATION_CACHE` paths in the host environment. Pass the same cache to
setup. Restart your ComfyUI process after installing the nodes; do not stop
another user's server. Refresh the browser and load the example workflow.

`auto` resolves CUDA, then Apple MPS, then CPU. Explicit unavailable devices fail
instead of silently switching. CUDA hosts need a compatible PyTorch wheel in
the worker; only Apple MPS has real-model verification on this checkout. CPU is
supported but can be slow. The worker logs its resolved device and elapsed time
in the inference provenance; the host logs the result. ComfyUI cancellation
terminates the worker process group on macOS/Linux, releasing accelerator memory.
Windows terminates the main worker only; process-tree cancellation is not verified.

Allow several minutes for a first run. The clean-install fast-mode check took
about 122 seconds end to end on Apple Silicon (116 seconds in the worker),
although earlier runs on the same sample were faster. The node can remain at
0% until inference completes; that alone does not indicate a stalled process.

## Quality and Geometry

`full (1.5 mm)` uses the standard five-model CT task; `fast (3 mm)` uses its
single lower-resolution checkpoint and is the default. Both return labels on
the original scan grid. Full is the backend's full-quality mode, not native CT
resolution inference. Increasing mesh detail does not recover anatomy missing
from the source or model; the public sample has 5 mm slice spacing.

The adapter writes original HU through SimpleITK to NIfTI (LPS to RAS and zyx to
xyz handled by the file format), validates discrete label IDs, and restores any
changed output geometry with nearest-neighbor resampling. Oblique geometry,
origin, spacing, series identity and source files are retained. Segmentation and
boolean mask contracts are separate from HU volumes.

Masks mesh at 0.5, default step 1, with zero padding and a compensated origin.
Disconnected regions are retained. No smoothing, hole filling, component removal
or decimation is applied. Boundary-touching masks produce a host warning: a
closed mesh can still represent cropped anatomy. The existing LPS mm to
`(-L,S,P)` metre conversion and core MESH/SaveGLB contracts are reused unchanged.

Groups are fixed label-ID unions: left lung, right lung, both lungs, all ribs and
thoracic vertebrae. A union is one mesh, without separately colored materials.
Absent anatomy yields an empty mask and an explanatory no-surface error when
meshed. Unsupported names are rejected. This is nonclinical software.

## Offline Use and Troubleshooting

Inference has no downloads: dependencies are imported only in the worker, models
are checked before inference, usage telemetry is disabled, and external socket
connections are blocked in the worker and its spawned Python processes. Local
IPC remains allowed for nnU-Net. Temporary CT/prediction files are deleted when
the adapter exits, including cancellation. There is no persistent prediction
cache beyond ComfyUI's graph cache. Model file stats, manifest and worker source
participate in cache invalidation; full hashes are verified on inference.

- Missing dependencies/weights: run setup for the chosen quality and verify the
  configured worker/cache paths. No downloads happen during node discovery.
- Incomplete/corrupt weights: remove only the named model's dataset directory
  inside this dedicated cache, then rerun setup. Do not edit checksum manifests.
- Device memory errors: select fast quality or CPU. The worker exits after each
  inference, so its model does not remain resident between graph runs.
- Absent anatomy: confirm scan coverage and selection; a valid empty mask is not
  a mesh. Boundary warnings indicate potentially truncated structures.

## Verification

```sh
.venv/bin/python -m pytest -q --tb=short
.venv/bin/python scripts/verify_segmentation.py --input-root /path/to/ComfyUI/input --output artifacts/segmentation-check/fast
```

The second command runs the real model, writes label NIfTI, physical-aspect
axial/coronal/sagittal overlays, counts, geometry, model/device/runtime provenance,
and sample attribution. Add `--quality full` for the five-model run. See
`VERIFICATION.md` for tested results and known limits.

Keep `SAMPLE_DATA.md` attribution with sample-derived exports. Model terms and
requested scientific citations are in `THIRD_PARTY_NOTICES.md`.
