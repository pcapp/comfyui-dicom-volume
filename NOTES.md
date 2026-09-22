# Milestone Notes

## Task 4: Implementation Update, 2026-09-22

Implemented the plan below using an isolated TotalSegmentator 2.18.0 worker,
three V3 nodes, a single organ/group dropdown, and the existing core mesh exporter.
Both full and fast standard CT models are installed locally and hash-pinned.
93 tests pass; real MPS inference, queued GLB exports, cache reuse, cold restart,
cancellation and Chrome dropdown/preview interaction were checked. See
[setup and usage](SEGMENTATION.md) and [actual evidence and limits](VERIFICATION.md).
Peter explicitly accepted Step 4 and requested its commit on 2026-09-22.
Finer-grained segmentation is deferred to a future pass. Incremental inference
percentage reporting is also a known follow-up; the current node can show 0%
until inference finishes. The earlier planning note is retained as history.

## Task 4: Organ Segmentation (Planned)

Peter requested TotalSegmentator-based selection and meshing of specific organs.
The [Task 4 execution plan](TASK_4_SEGMENTATION_PLAN.md) is the handoff for Astra6.
It covers optional model setup, standard-task licensing, geometry preservation,
reusable organ selection, mask meshing, and real-host verification. Implementation
has not started; earlier milestone acceptance remains independently recorded.

## Part Two: Volume to Mesh

- Current implementation supersedes the earlier dependency and frontend notes:
  scikit-image 0.26.0 is now a runtime requirement; the host frontend reports
  1.53.6. The extension remains on its existing Python 3.14.2 environment and the
  host on Python 3.13.13. Host installation was additive, with no host sync.
- Inspected installed `nodes_hunyuan3d.py`, `nodes_load_3d.py`,
  `geometry_types.py`, `_io.py` and `nodes_save_3d.py`. SaveGLB has moved to the
  latter module. Its MESH uses batched tensors, preserves coordinates, and
  returns a `3d` UI payload with no graph outputs. Preview3D accepts files/paths,
  not MESH. The installed frontend's SaveGLB extension provides the preview.
- Pure meshing lives in `meshing.py`; the small V3 adapter in `nodes.py` supplies
  the host's `io.Mesh.Type`. Marching cubes operates on original HU values,
  defaults to 200 HU and step 2, and excludes degenerate faces. Physical LPS mm
  coordinates are transformed once, then rotated to `(-L,S,P)` and converted to
  metres for glTF. No centering, normalization or custom viewer/exporter.
- Right-hand face winding is corrected for the `(z,y,x)` permutation and any
  reflected direction. Gradient normals use the inverse transpose. Closed
  synthetic shapes verify orientation, anisotropy, origin, obliquity, physical
  bounds and topology. The host smoke script also checks the actual GLB bytes.
- Consulted current official [SaveGLB documentation](https://github.com/Comfy-Org/embedded-docs/blob/main/comfyui_embedded_docs/docs/SaveGLB/en.md),
  [marching-cubes API](https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.marching_cubes),
  [frontend SaveGLB source](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/src/extensions/core/saveMesh.ts)
  and [glTF coordinate/unit specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#coordinate-system-and-units).
  Installed code was the authority for this host's contracts.
- See `VERIFICATION.md` for automated checks and the user's mesh acceptance.
  User-observed saved-workflow restart remains unreported. Implementation made
  no ComfyUI core edits or slice-viewer changes.

## API and Design

- Inspected installed ComfyUI revision
  `95539f56344958339e39b7582a476267d489b0ee` and current online walkthrough,
  V3 migration, Registry specifications and standards on 2026-09-22.
- `comfy_api/latest/_io.py`: `Schema.is_output_node` (around line 1731)
  enables standalone execution without removing outputs. `fingerprint_inputs`
  (around line 2317) returns a changing fingerprint, not a boolean flag.
  `NodeOutput` accepts a returned volume together with `ui.PreviewText`.
- `comfy_api/latest/__init__.py` defines `ComfyExtension`; its
  `get_node_list` is async. The entry point is deliberately lazy so plain-loader
  unit tests do not import host modules. No legacy node mappings or PyPI
  `comfy_api` dependency are needed.
- The installed frontend 1.43.18 contains `isApiJson` and `loadApiJson` in
  `static/assets/dialogService-DSBgqcNn.js`. The example uses that actual prompt
  format (`class_type`, `inputs`, `_meta`), not an invented frontend graph schema.
  Browser import is still pending.
- `folder_paths.get_input_directory()` honors the configured input root.
  Annotated-file helpers allow input/output/temp semantics unsuitable for a
  constrained relative directory, so containment is explicitly checked here.
- Geometry validation uses DICOM header positions, orientation and spacing before
  pixel decoding, then compares the decoded affine to every slice position.
  Position tolerance: 0.001 mm or 0.1% of z spacing for regularity; decoded plane
  positions must agree within 0.001 mm. These accommodate decimal rounding, not
  quality recommendations. Sheared stacks are rejected; oblique grids are retained.
- Test fixture writing initially exposed implicit-VR output and the writer's
  inverse rescaling behavior. Fixtures now write known int16 stored pixels with
  identity rescale, then patch only the two implicit-VR DS tags using `struct`.
  Tests verify the written tags and actual pixel bytes before calculating expected
  HU independently. Fractional and per-slice rescale tests pass.
- Runtime dependencies are only NumPy and SimpleITK; pytest is a dev dependency.
  `requirements.txt` and `pyproject.toml` share the same lower bounds. `uv.lock`
  pins the tested extension environment. Host dependency installation is additive
  via `uv pip install --python`, never host `uv sync`.
- Registry publishing is out of scope. No repository URL or PublisherId has been
  invented; these would be required before eventual Registry publication.

## Environment and Actual Checks

- Starting extension state was clean `main`; while working, the branch changed
  externally to `feat/load-slices`. Peter explicitly confirmed keeping that branch.
  No commits, pushes or host edits were made.
- PyCharm configured the extension's isolated uv environment:
  `/Users/peter/repos/comfyui-dicom-volume/.venv/bin/python`, Python 3.14.2.
  Installed/tested: NumPy 2.5.3, SimpleITK 2.5.6, pytest 9.1.1.
- `uv sync` completed. Exact offline check:
  `/Users/peter/repos/comfyui-dicom-volume/.venv/bin/python -m pytest -q --tb=short`
  returned **28 passed**. `git diff --check` passed.
- Host SDK query returned "File is not part of any module" for ComfyUI/main.py.
  Existing host `.venv/pyvenv.cfg` says Python 3.13.3; installed frontend metadata
  says 1.43.18. These are inspected facts, not a verified host launch.
- Host has an existing modified `pyproject.toml` adding a uv workspace member.
  It is preserved. Symlink destination was absent and port 8188 was free when
  inspected. Recheck both immediately before setup.
- TCIA v4 public metadata confirms the requested series, 148 images, 77,759,514
  source bytes and CC BY 3.0. Sample download and actual geometry remain pending.
  No sample download or host setup command has been run on Peter's behalf.

### Host Interpreter Repair, 2026-09-22

Peter reported an interpreter-check error and authorized repair. The host's
`.venv/bin/python` linked to a missing Homebrew Python 3.13 executable. Repointed
it to installed uv Python 3.13.13 and updated `.venv/pyvenv.cfg` to match,
preserving installed packages. The absolute interpreter check now passes and
reports frontend 1.43.18, NumPy 2.4.4 and PyTorch 2.11.0. SSL and SQLite imports
and a small PyTorch tensor calculation passed. Host Git status still shows only
the pre-existing `pyproject.toml` modification. Host launch and node integration
remain pending. PyCharm still reports that host `main.py` is outside its modules;
this repair verifies the terminal interpreter, not IDE SDK configuration.

### Sample Archive Fix, 2026-09-22

The real NBIA archive contains 148 DICOM files totaling the published 77,759,514
bytes plus a 2,793-byte root `LICENSE`. Extraction now preserves that license
while checking DICOM counts and sizes separately; provenance records its local
checksum separately. All 30 tests passed. Diagnostic extraction and volume
verification under `/private/tmp` passed, including exact source-plane equality.
Host sample installation and human acceptance remain pending.

## Review and Local Commits

After manual acceptance, Peter can review `git diff`, `git diff --check`, and
`git status --short`, then make these local commits on the chosen feature branch:

1. `Add V3 CT DICOM volume loader with geometry and HU tests`:
   loader.py, nodes.py, __init__.py, tests/test_loader.py, pyproject.toml,
   requirements.txt, uv.lock, .gitignore, LICENSE, README.md.
2. `Add attributed TCIA sample retrieval and verification workflow`:
   scripts/, tests/test_fetch_sample.py, tests/test_verification.py,
   example_workflows/, SAMPLE_DATA.md, VERIFICATION.md, NOTES.md.

Review file lists explicitly; do not stage input DICOM, generated artifacts,
virtual environments, or the host integration symlink. No remote publishing.
