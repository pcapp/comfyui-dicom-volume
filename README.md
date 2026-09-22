# DICOM Volume

Load conventional CT and extract an HU isosurface in ComfyUI:
`Load DICOM Volume -> Volume to Mesh -> Save 3D Model (SaveGLB)`.
The core save node writes a GLB and supplies its existing interactive preview.
**Not for clinical use.**

## Setup

Use an existing ComfyUI checkout and its verified interpreter. Preserve local
changes; no host upgrade or environment replacement is required. From this
extension checkout:

```sh
EXTENSION_ROOT="$PWD"
COMFY_ROOT="/path/to/ComfyUI"
git status --short --branch
git -C "$COMFY_ROOT" status --short --branch
"$COMFY_ROOT/.venv/bin/python" -c 'import sys; print(sys.executable, sys.version)'
```

Link this checkout into the host's `custom_nodes` only if no entry already exists:

```sh
ln -s "$EXTENSION_ROOT" "$COMFY_ROOT/custom_nodes/comfyui-dicom-volume"
uv pip install --python "$COMFY_ROOT/.venv/bin/python" -r requirements.txt
```

Runtime requirements are NumPy, SimpleITK and scikit-image. PyTorch and `comfy_api`
come from ComfyUI; do not install a PyPI package named `comfy_api`. Do not run
`uv sync` against the shared host environment. The extension's separate test
environment is managed with `uv sync --locked`.

Restart your own host after Python changes. CPU execution is sufficient and no
diffusion models are required. For a new host, select a free port, then run:

```sh
cd "$COMFY_ROOT"
"$COMFY_ROOT/.venv/bin/python" main.py --cpu --disable-api-nodes --listen 127.0.0.1 --port 8188
```

Do not stop an unrelated process. Open the URL printed by the host.

## Run the Workflow

1. Read [SAMPLE_DATA.md](SAMPLE_DATA.md) for the public sample, its explicit
   downloader, TCIA citation, CC BY 3.0 license and usage policy. Put a supported
   series beneath the host's input directory; refresh the browser after adding
   folders. The nodes never download data.
2. Open or drag `example_workflows/dicom_to_mesh.json` onto the ComfyUI canvas.
   This is API-format JSON supported by the installed frontend. Select the
   input folder in `Load DICOM Volume`; the example uses `tcia-med-lymph-073`.
3. Run with `threshold_hu=200` and `step_size=2`. SaveGLB appears as
   `Save 3D Model` and displays the saved mesh in its embedded preview. Files
   default to `output/dicom/volume_00001_.glb`, with an incrementing counter.
   A separate Preview3D node is unnecessary and does not accept MESH directly.

The threshold acts on original HU values. A higher threshold changes the surface;
this is not anatomical segmentation. Step 1 samples every voxel; larger integer
steps run faster and may miss thin structures. Cropped anatomy can produce open
surfaces. Marching cubes may skip a trailing voxel interval when its length is
not divisible by the step. Nothing is padded, capped, cropped, smoothed,
decimated or resampled by the extension.
No surface means adjusting the threshold or reducing the step, not fabricating
geometry. The volume and mesh must fit in RAM.

Retain [sample attribution and policy](SAMPLE_DATA.md) with sample-derived meshes,
images and screenshots. Generated data and reports belong under ignored
`artifacts/` (or the host output directory), never in commits. DICOM metadata and
derived geometry can be identifying; public availability is not a privacy audit.

## Coordinates and Units

`loader.Volume` is unchanged:

| Field | Meaning |
| --- | --- |
| `voxels` | NumPy float32 HU, indexed `(z,y,x)` |
| `spacing` | `(x,y,z)` voxel spacing in mm |
| `origin` | Voxel `(0,0,0)` position in DICOM LPS mm |
| `direction` | Row-major 3x3 matrix; columns give physical x/y/z directions |
| `series_uid` | Selected series UID |
| `source_files` | Files in GDCM spatial order |

Physical position is `origin + direction @ ([x,y,z] * spacing)`.
Meshing explicitly permutes marching-cubes `(z,y,x)` coordinates and applies this
affine once. Winding is reversed when that transform reflects coordinates;
gradient normals use its inverse transpose and are renormalized.

The MESH adapter outputs `(X,Y,Z)=(-L,S,P)/1000`: right-handed metres, superior up,
anterior toward negative Z. The rotation preserves handedness. Origin is retained;
there is no centering or dimension normalization. Inverse mapping to DICOM mm is
`(L,P,S)=1000*(-X,Z,Y)`. The core exporter writes positions unchanged.
[glTF specifies metres and a right-handed Y-up coordinate system](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#coordinate-system-and-units).
The host viewer may frame the object for display; the saved GLB retains physical
coordinates. Use core SaveGLB for this coordinate-preserving export.

## Verification and Limits

From the extension checkout:

```sh
uv sync --locked
.venv/bin/python -m pytest -q --tb=short
```

See [VERIFICATION.md](VERIFICATION.md) for actual evidence, the host smoke command,
mesh inspection and restart acceptance. `example_workflows/load_dicom_volume.json`
still runs the loader alone and displays its geometry/HU summary.

The loader selects the largest eligible conventional single-frame CT series,
breaking ties by ascending UID. It excludes localizers and other modalities,
checks containment (including symlinks), recognizes extensionless DICOM, validates
regular geometry and retains oblique orientation and fractional HU. GDCM applies
slope/intercept once. A file-stat fingerprint invalidates ComfyUI's own cache;
there is no duplicate volume cache.

At least two slices are required. Enhanced/multiframe CT, irregular/duplicate
positions, varying orientation or spacing, and gantry shear require an appropriate
regular reconstruction. An interactive slice viewer is future work.

Code: [MIT](LICENSE). Sample data has its own attribution and license.
