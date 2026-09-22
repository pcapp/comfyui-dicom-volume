# DICOM Volume

`Load DICOM Volume` loads a conventional CT series from ComfyUI's input directory
into one `VOLUME` output. It runs on its own and reports the selected series,
slice count, shape, spacing, dtype and HU range in the host log. It also returns
the supported V3 text-preview payload. **Not for clinical use.**

## Setup

The extension repo owns the source; ComfyUI is the host application. A symlink
lets the host discover this source without copying it into the ComfyUI repo.
The extension's `.venv` is for unit tests. ComfyUI uses the interpreter that
launches `main.py`, so it needs the runtime requirements separately.

Work through these checkpoints with observations after each one. Commands below
use Peter's local paths; verify the host interpreter before installing anything.

1. In `/Users/peter/repos/comfyui-dicom-volume`, run
   `git status --short --branch`. Peter's confirmed branch is `feat/load-slices`;
   keep it and preserve existing changes.
2. Inspect the host with `git -C /Users/peter/repos/ComfyUI status --short --branch`
   and `git -C /Users/peter/repos/ComfyUI rev-parse HEAD`. Do not pull or discard
   modifications. Inspect the existing environment, then confirm it with:
   `/Users/peter/repos/ComfyUI/.venv/bin/python -c 'import sys; from importlib.metadata import version; print(sys.executable); print(sys.version); print("frontend", version("comfyui-frontend-package"))'`.
   Expect the host `.venv` path and frontend version. If it fails, stop here and
   inspect that environment rather than replacing it.
3. Check `ls -ld /Users/peter/repos/ComfyUI/custom_nodes/comfyui-dicom-volume`.
   If absent, run
   `ln -s /Users/peter/repos/comfyui-dicom-volume /Users/peter/repos/ComfyUI/custom_nodes/comfyui-dicom-volume`.
   Confirm using `readlink /Users/peter/repos/ComfyUI/custom_nodes/comfyui-dicom-volume`;
   expect `/Users/peter/repos/comfyui-dicom-volume`. If already present, inspect it;
   never overwrite it. Do not commit this integration link to ComfyUI core.
4. From `/Users/peter/repos/ComfyUI`, install into the verified host interpreter:
   `uv pip install --python /Users/peter/repos/ComfyUI/.venv/bin/python -r /Users/peter/repos/comfyui-dicom-volume/requirements.txt`.
   This installs NumPy and SimpleITK into the process that runs the node. Do not
   use `uv sync` on this shared host environment or install `comfy_api` from PyPI.
5. Check port 8188 with `lsof -nP -iTCP:8188 -sTCP:LISTEN`. If unused, launch from
   `/Users/peter/repos/ComfyUI`:
   `/Users/peter/repos/ComfyUI/.venv/bin/python main.py --cpu --disable-api-nodes --listen 127.0.0.1 --port 8188`.
   Expect `http://127.0.0.1:8188` and no extension import error. If occupied, pick
   another free port and use its URL. Do not stop another server. CPU is sufficient;
   no diffusion models are needed. Python edits require a host restart, not just
   a browser refresh. Search for `Load DICOM Volume` after launch.

## Public Sample

Read [SAMPLE_DATA.md](SAMPLE_DATA.md) before fetching. The explicitly invoked
script downloads only CT Lymph Nodes case `MED_LYMPH_073`, series
`61.7.338133024060269626651520600539598241004`: 148 images, approximately 78 MB of
source DICOM, to `/Users/peter/repos/ComfyUI/input/tcia-med-lymph-073`.
The ZIP transfer size is recorded after download. Data license: CC BY 3.0.

From `/Users/peter/repos/comfyui-dicom-volume`, after unit-test environment setup:

```sh
/Users/peter/repos/comfyui-dicom-volume/.venv/bin/python scripts/fetch_sample.py
```

Expect 148 files, verified ZIP CRCs, and `provenance.json` with local SHA256 values.
Existing data is never overwritten. If download verification fails, inspect the
error before retrying. Suitability is pending until decoding and geometry checks
pass; public metadata alone is insufficient. The node never downloads anything.

## Verification

For the isolated extension test environment, run `uv sync --locked` in this repo,
then `/Users/peter/repos/comfyui-dicom-volume/.venv/bin/python -m pytest -q`.
Tests are offline and generate small synthetic DICOM files with SimpleITK.

Follow [VERIFICATION.md](VERIFICATION.md) for the one-node workflow, sample report,
PNG inspection, restart check, and separate human acceptance record.

## VOLUME Contract

`loader.Volume` holds:

| Field | Meaning |
| --- | --- |
| `voxels` | NumPy `float32` HU array, indexed `(z, y, x)` |
| `spacing` | `(x, y, z)` voxel spacing in millimetres |
| `origin` | Physical position of voxel `(0, 0, 0)` in DICOM LPS mm |
| `direction` | Row-major 3x3 matrix; columns give physical x/y/z axis directions |
| `series_uid` | Selected DICOM SeriesInstanceUID |
| `source_files` | Selected files in GDCM spatial order |

For array index `[z, y, x]`, physical position is
`origin + direction.reshape(3, 3) @ ([x, y, z] * spacing)`.
Future meshing must account for the axis-order difference and retain this affine.
GDCM applies slope/intercept once; the output is explicitly float32. No cropping,
windowing, normalization, resampling or reorientation is applied to the volume.

## Limits

The largest eligible CT series wins; ties use ascending SeriesInstanceUID.
Localizer/scout images and other modalities are excluded. Files must stay within
the configured input root, including symlink targets. Discovery reads headers
without decoding pixels and recognizes extensionless DICOM files. Directory
symlinks are not traversed during discovery. A file-stat manifest invalidates
ComfyUI's normal cache on additions, removals, replacements or metadata changes.
There is no additional global volume cache.

This milestone supports scalar conventional single-frame CT stacks with at least
two slices. Enhanced/multiframe CT, irregular positions, duplicate positions,
changing orientation/spacing, and gantry shear need a suitable exported regular
reconstruction. Consistent oblique stacks are supported. The complete volume
must fit in RAM. Refresh the browser after adding new input folders.
Meshing and an interactive slice viewer are subsequent work.

Code: [MIT](LICENSE). Sample data has its own attribution and license, below.
