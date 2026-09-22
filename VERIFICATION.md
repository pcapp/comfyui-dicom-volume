# Verification

What was tested, on what, and how to reproduce it. These are engineering checks,
not medical validation. Sample-derived results use the public TCIA series
described in [SAMPLE_DATA.md](SAMPLE_DATA.md).

## Tested Environment

| Component | Version |
| --- | --- |
| ComfyUI | 0.37.0 (`95539f56344958339e39b7582a476267d489b0ee`), frontend 1.53.6 |
| Host | macOS on Apple Silicon, Python 3.13, PyTorch 2.14 (fresh install) |
| Segmentation worker | Python 3.12, TotalSegmentator 2.18.0, torch 2.14.0, nnunetv2 2.8.1, MPS |
| Sample | TCIA `MED_LYMPH_073`: 148 slices, `(148, 512, 512)`, spacing `(0.852, 0.852, 5.0)` mm |

Not tested: Windows, ComfyUI Desktop/portable, Linux, CUDA, and end-to-end CPU
segmentation.

## Clean-Install Check

A fresh HTTPS clone of this repository was installed next to a fresh upstream
ComfyUI clone, with new Python environments, a newly downloaded sample and empty
model caches, following [README.md](README.md) and [SEGMENTATION.md](SEGMENTATION.md)
exactly. A fresh automated Chrome profile drove the real UI.

| Check | Result |
| --- | --- |
| Install | Extension installed as documented; no Node build step required. |
| Sample download | 148 DICOM files, 77,759,514 bytes; metadata, ZIP and attribution checks passed. |
| HU mesh workflow | Example imported via the file input and run. 224,036 vertices, 447,879 triangles; exported GLB positions and indices exactly match an independent mesher run. |
| Slice viewer | Axial, coronal and sagittal planes rendered; window changes updated pixels; no browser JavaScript errors. |
| Organ workflow (fast) | Heart, both lungs and aorta exported. First inference about 116 s on MPS. |
| Organ workflow (full) | All three branches exported; inference about 123 s on MPS. |
| Graph caching | Switching heart to left lung reused the cached inference; rerun took 0.4 s. |
| Restart | Saved graph reloaded after a host restart with all 11 nodes and selections intact; reran successfully. |

## Automated Tests

```sh
uv sync --locked
.venv/bin/python -m pytest -q --tb=short
npm ci && npm run typecheck && npm test
```

93 Python tests cover DICOM series selection, HU conversion, geometry (anisotropic,
oblique and reflected), slice extraction, HTTP route validation, the volume
registry, meshing (winding, normals, physical bounds), segmentation label
handling, model manifests, the offline guard and worker cancellation. Frontend
tests cover windowing, aspect, the slice cache and viewer interaction in jsdom.

Selected results from host integration runs:

- **Slice route:** every tested plane is byte-identical to direct extraction; bad
  parameters return 400, expired handles 410, mismatched Origin 403.
- **Mesh export:** GLB bounds equal the physical LPS bounds converted to glTF
  `(-L,S,P)` metres, with no centering. Repeat runs are byte-identical.
- **Segmentation:** labels return on the original scan grid with original HU
  preserved. No organ-accuracy claim is made; there is no ground truth here.

## Reproduce Host Checks

Each script takes an explicit ComfyUI path or input directory and writes a report
under ignored `artifacts/`. Use a new output directory per run.

```sh
COMFY_ROOT="/path/to/ComfyUI"
.venv/bin/python scripts/verify_volume.py tcia-med-lymph-073 --input-root "$COMFY_ROOT/input"
"$COMFY_ROOT/.venv/bin/python" scripts/verify_mesh.py --host-root "$COMFY_ROOT" --server http://127.0.0.1:8188 --output artifacts/mesh-check
.venv/bin/python scripts/verify_slices.py --help
.venv/bin/python scripts/verify_segmentation.py --input-root "$COMFY_ROOT/input" --output artifacts/segmentation-check/fast
```

## Known Limits

- The sample's 5 mm slice spacing produces visible steps; nothing smooths them.
- The segmentation node can show 0% until inference finishes.
- The core 3D preview's default framing can clip large meshes; zoom out.
- Windows cancellation stops the main worker only; the process tree is not verified.
