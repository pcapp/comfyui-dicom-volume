# Manual Integration and Acceptance

## Part Two: Mesh Evidence, 2026-09-22

Automated mesh checks pass. The user supplied screenshots of the connected
three-node workflow and rendered mesh, explicitly accepted the milestone
("From an acceptance test this is great. It works."), and subsequently reported
that the observed step-size behavior makes sense. Exact compared step values
were not recorded. User-observed saved-workflow restart remains unreported;
automated cold-restart evidence is recorded separately below.

| Check | Actual evidence |
| --- | --- |
| Offline suite | `.venv/bin/python -m pytest -q --tb=short`: 54 passed, including 24 meshing cases. scikit-image emits 58 NumPy 2.5 deprecation warnings in the Python 3.14.2 extension environment. |
| Host | Revision `95539f56344958339e39b7582a476267d489b0ee`, Python 3.13.13, PyTorch 2.11.0, NumPy 2.4.4, scikit-image 0.26.0, frontend **1.53.6** (rechecked; differs from the earlier record below). |
| Host isolation | Separate CPU host on port 8189 with output/temp/user directories under ignored `artifacts/mesh-verification`; only this extension whitelisted; metadata disabled. Existing port 8188 process untouched. |
| Synthetic host adapter/export | Real host MESH: float32 vertices/normals `(1,N,3)`, int64 faces `(1,F,3)`. Core exporter round-trip: 102 vertices, 200 triangles; exact position/index equality; outward winding, unit normals and physical dimensions pass. |
| Actual queued workflow | `Load DICOM Volume -> Volume to Mesh -> SaveGLB`, 200 HU, step 2: host status `success`; valid `3d` filename/subfolder/type preview payload; GLB fetched through host `/view`. |
| Sample geometry | 224,036 vertices, 447,879 triangles, 10,752,552-byte GLB. Dimensions `(X,Y,Z)` approximately `(0.42290145, 0.73000002, 0.27724800)` m. Binary positions and indices exactly match the separately run mesher; normals match and are finite/unit length. |
| Physical bounds | LPS mm minimum `(-217.86009, -264.70923, -563.5)`, maximum `(205.04134, 12.53877, 166.5)`. Stored GLB bounds match `(-L,S,P)/1000`, with no node transforms or centering. |
| Local artifacts | `artifacts/mesh-verification/check-3/report.json`, `sample.glb`, and accompanying `ATTRIBUTION.md`. Generated data is ignored and untracked. |
| Cold restart | Stopped/relaunched the isolated host and reran `verify_mesh.py` into `check-4`: all checks passed again. `cmp` confirms byte-identical GLBs; SHA256 `6b2bfa3b227c817b54efa1c752c878fdd2955fa98a3d6a8c8c722973f8b3840d`. The temporary server was then stopped; this is automated restart evidence, not a user observation. |
| Preview and acceptance | User screenshots show the connected workflow at 200 HU, step 2 and a rendered mesh in Save 3D Model; a later close-up shows additional inspection. User explicitly accepted the working mesh milestone. Agent browser automation was blocked; exact workflow import and save/reopen steps were not reported. |

The real sample initially exposed three unused marching-cubes vertices whose
area-weighted normals were zero after degenerate-face removal. The final code
uses marching-cubes gradient normals, transformed by the inverse transpose of
the physical affine. The final sample check passes for every vertex. No surface
vertices or faces are removed by extension code. Closed synthetic shapes, not
cropped anatomy, establish winding and topology.

### Reproduce the Host Check

From the extension checkout, with a fresh local host already running (replace
the host path and port as needed):

```sh
COMFY_ROOT="/path/to/ComfyUI"
"$COMFY_ROOT/.venv/bin/python" scripts/verify_mesh.py --host-root "$COMFY_ROOT" --server http://127.0.0.1:8189 --output artifacts/mesh-check
```

Use a new output directory for each run. The script performs a synthetic host
adapter/export check, queues the example, downloads only the local exported GLB,
compares binary geometry, and writes a report plus sample attribution. Use the
existing public sample. This does not certify that a dataset lacks identifiers.

### Manual Check Procedure

Mesh acceptance is recorded above. The saved-workflow restart portion remains
available as an additional manual check; do not infer that it was performed.

1. Restart your own ComfyUI host to load the new Python node. Refresh the browser
   and open `example_workflows/dicom_to_mesh.json` via Open or drag-and-drop.
2. Run at 200 HU, step 2. Confirm that Save 3D Model shows a mesh, and rotate/zoom
   it. Record any distortion, missing surfaces or errors. Threshold surfaces are
   not segmentation; larger steps can omit thin structures, and scan boundaries
   can leave open surfaces.
3. Save the workflow, stop/relaunch your host, reopen it and run again. Record
   whether the nodes, controls, preview and saved GLB still work.
4. Explicitly accept or reject the mesh milestone. Automated checks above do
   not replace these observations. Retain sample attribution with shared images.

## Part One: Historical Evidence

The following is the earlier loader record. Subsequently, the user reported
that all four PNGs open; this does not establish acceptance of anatomy, geometry
or image quality. Final visual/restart acceptance remains unrecorded.

Status: offline tests, ComfyUI sample execution and volume verification passed.
Peter reported successful verification and supplied a screenshot of the completed
ComfyUI workflow on 2026-09-22, then requested a commit. PNG inspection, host
restart verification and final human acceptance remain unrecorded.

1. Open the local URL printed by ComfyUI. Import
   `example_workflows/load_dicom_volume.json` using the workflow Open command or
   drag it onto the canvas. This is ComfyUI API-format JSON, supported by the
   installed frontend's `isApiJson`/`loadApiJson` path. Expect one
   `Load DICOM Volume` node. Report missing-node errors or unexpected widgets.
2. After the explicit sample download, refresh the page, select
   `tcia-med-lymph-073`, and queue the workflow. Expect successful execution.
   Read the host log's `Load DICOM Volume` summary. Confirm the selected UID is
   `61.7.338133024060269626651520600539598241004`, count is 148, shape begins with
   148, and dtype is float32. Record the actual full shape, spacing and HU range;
   do not infer those values from a plausible-looking scan.
3. From `/Users/peter/repos/comfyui-dicom-volume`, run:
   `/Users/peter/repos/comfyui-dicom-volume/.venv/bin/python scripts/verify_volume.py tcia-med-lymph-073`.
   Expect `artifacts/sample-verification/report.json`, four PNGs, and an exact
   numerical match between the loaded middle plane and its independently read
   source DICOM file. The report includes selected DICOM geometry/rescale tags,
   physical positions and display windows. Compare it with the node's summary and
   downloaded provenance. If output already exists, select a fresh directory with
   `--output artifacts/sample-verification-2`; no artifacts are overwritten.
4. Open `first-soft.png`, `middle-soft.png`, `last-soft.png` and `middle-bone.png`
   in the report folder. Review stored-axis first/middle/last slices. Soft-tissue
   window: center 40 HU, width 400 HU. Bone window: center 400 HU, width 1800 HU.
   Display pixels preserve physical in-plane aspect, with nearest-neighbor display
   resizing only; HU data is unchanged. Images have no claimed anatomical labels.
   Record what you see, including obvious distortion, unexpected empty planes or
   discontinuities. Visual inspection complements the numerical geometry/HU checks.
5. Save the workflow in ComfyUI, stop your host with Ctrl-C, relaunch using the same
   absolute interpreter and command, reopen the saved workflow and queue again.
   Expect the same selected series and summary. Record the result and explicitly
   state whether you accept the milestone after all checkpoints pass.

## Evidence Record

| Check | Evidence | Status |
| --- | --- | --- |
| Offline synthetic tests | `python -m pytest -q`: 30 passed on 2026-09-22, including ZIP license handling and DICOM size mismatch regression checks | Passed |
| ComfyUI revision | Inspected `95539f56344958339e39b7582a476267d489b0ee`; Peter supplied a successful runtime screenshot | Runtime observed |
| Frontend | Repaired host interpreter reports installed package version 1.43.18; Peter's screenshot shows the loader on the canvas | Browser observed |
| Host interpreter | On 2026-09-22, repaired the broken Homebrew link using installed uv Python 3.13.13 and updated `pyvenv.cfg`. Absolute interpreter check passed; `sys.prefix` remains the host `.venv`. NumPy 2.4.4, PyTorch 2.11.0, SSL and SQLite imports passed; tensor calculation returned `[2.0, 4.0]`. | Runtime check passed; host launch pending |
| Symlink and dependency installation | Symlink points to this extension repo; Peter's screenshot shows successful node execution | Integration passed |
| Workflow import and node search | Peter's screenshot shows `Load DICOM Volume` with `tcia-med-lymph-073` selected; exact import/search steps not reported | Node present in browser |
| Public sample download and geometry | Fixed ZIP license handling; verified 148 DICOM files totaling 77,759,514 bytes. Peter's successful host execution and local verification report confirm the installed sample has the expected geometry. | Passed |
| Diagnostic source-plane comparison | `/private/tmp/dicom-download-check-2yulumd9/report/report.json`: exact middle-plane match, 0 HU difference | Automated check passed; human review pending |
| Sample execution and report | Peter reported successful `verify_volume.py` execution. Local `artifacts/sample-verification/report.json` agrees with the screenshot: 148 slices, shape `(148, 512, 512)`, spacing `(0.8515625, 0.8515625, 5.0)` mm, float32, HU `[-1024, 3071]`; independent plane 74 matches exactly (0 HU error). Four PNGs generated. | Passed |
| Human PNG inspection | No user observation yet | Pending |
| Host restart and saved workflow | No user observation yet | Pending |
| Peter's explicit acceptance | Commit requested after successful verification; final acceptance of PNG inspection and restart not stated | Remaining acceptance pending |

Only replace pending human rows using Peter's actual observations. Automated
smoke checks are separate evidence and cannot stand in for human acceptance.
