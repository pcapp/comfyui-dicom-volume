# Manual Integration and Acceptance

## Task Four: Organ Segmentation, 2026-09-22

Implemented optional TotalSegmentator 2.18.0 standard CT `total`, with separate
inference, single-dropdown anatomy selection, and mask-meshing V3 nodes.
Existing loader/HU behavior and the user's pre-existing NOTES/plan work were
preserved. No ComfyUI core/package changes or publishing occurred during
implementation. Peter explicitly accepted Step 4 on 2026-09-22 and authorized
its commit, deferring finer-grained segmentation to a later pass.

| Check | Actual evidence |
| --- | --- |
| Offline regression | 93 passed, 63 upstream scikit-image/NumPy deprecation warnings. Includes 22 new tests: independent NIfTI RAS landmarks, anisotropic/oblique/reflected geometry, nearest-neighbor restoration including same-shape changed-affine predictions, invalid labels, exact groups, empty anatomy, boundary padding at steps 1/2/3, winding/normals, disconnected components, cache identity, corrupt manifests, offline guard, and subprocess cancellation. |
| Environments | Extension Python 3.14.2 unchanged. Isolated worker Python 3.12.12: TotalSegmentator 2.18.0, torch 2.14.0, nnunetv2 2.8.1, NumPy 2.5.3, nibabel 5.4.2, SimpleITK 2.5.6. Complete macOS arm64 snapshot in requirements-segmentation-macos.lock.txt. Host retains Python 3.13.13 / torch 2.11.0. |
| Models | Standard tasks 291-295 (full, 1.5 mm) and 297 (fast, 3 mm) explicitly downloaded. Source URLs, all checkpoint/plans/dataset SHA-256 hashes and Apache-2.0 terms recorded in models/total-{full,fast}.json. Setup and inference verify pinned hashes. |
| Real sample | Both qualities ran on MPS, returned (148,512,512) labels on the original 0.8515625 x 0.8515625 x 5 mm LPS grid, and preserved original HU. Fast: heart 215,757 voxels, both lungs 1,576,884, aorta 70,065. Full: 228,243 / 1,582,738 / 70,130 respectively. None of these masks touched the scan boundary. |
| Runtime/memory | Fast worker inference 33.04 s initially and 14.86 s on a later run; full 126.28 s. Final fast worker peak resident memory 8,672,624,640 bytes (about 8.08 GiB), excluding child-process/host memory; not a VRAM measurement. Timing includes backend processing but excludes host serialization and mesh export. |
| Geometry/export | Queued example produced heart/lungs/aorta GLBs with exact position/index agreement against separately computed meshes, finite unit normals and physical metre coordinates. Fast meshes: 62,220 / 240,968 / 28,628 vertices; 124,448 / 482,056 / 57,252 triangles. |
| Cache | Heart-to-left-lung selection reused inference node 2 and untouched branches. Total queue round trip 0.69 s initially, 0.62 s after restart. Changing quality to full ran node 2 again (then deliberately cancelled). Model-file mutation invalidation is covered offline. |
| Cold restart/offline | Isolated host on 8189 restarted with final code; queued sample/export comparisons passed again in 22.57 s. Worker blocks external socket connections, including in spawned Python processes; weights were already installed, and telemetry disabled. The whole computer's network was not disabled. |
| Failure/cancellation | Actual full-quality host inference interrupted at node 2; history reported execution_interrupted within 516 ms of interrupt request. No segmentation/spawn workers remained afterwards. Explicit CUDA on this Mac returned the expected unavailable-device error. Missing/corrupt models, absent structures and bounded diagnostics are covered offline. |
| Visual inspection | Agent inspected axial/coronal/sagittal overlays for both qualities: alignment is visually plausible. Chrome/Playwright loaded the actual 11-node API example, executed it, and rendered the core heart/lung/aorta previews. Pointer rotation/zoom changed the heart view. Native dropdown selection changed heart to left lung and reran successfully. The core aorta preview's initial framing clips the upper arch; zoom works, but default framing remains a host-viewer limitation. No custom viewer changes. |

Evidence is ignored under `artifacts/segmentation-check/{fast,full,final-fast}`
(labels, overlays, full label counts, model/device/runtime reports and attribution)
and `artifacts/segmentation-host/{check,cold-restart}` (GLBs, exact comparisons,
cache reports and attribution). Browser screenshots and failure/cancellation
reports are in `artifacts/segmentation-host`. The first sandboxed inference
attempt failed because nnU-Net could not create its local multiprocessing socket;
the real runs used local IPC permission. The first sandboxed regression attempt
likewise failed only on the existing HTTP test's bind permission; the permitted
rerun passed. Neither failed attempt is counted as a successful integration.

Limits: no established organ ground truth or numerical accuracy claim. Peter's
acceptance covers Step 4 as implemented. The sample's 5 mm slice spacing produces visible
steps; no smoothing hides them. CUDA, Windows process-tree cancellation and
end-to-end CPU inference were not verified on this Mac. User-observed workflow
save/reopen acceptance remains pending. The independent existing host on 8188
was not stopped; isolated test hosts were stopped after verification.
Incremental inference percentage reporting is not implemented: the active
segmentation node can display 0% until it completes.

Reproduce backend and host checks using `scripts/verify_segmentation.py` and
`scripts/verify_segmentation_host.py`; see `SEGMENTATION.md` for setup. The host
check takes `--input-root`, `--labels` from the real fast run, and `--output`.

## Part Three: Slice Viewer Evidence, 2026-09-22

Implementation and automated integration pass. The user supplied a screenshot of
the working viewer and subsequently accepted Task 3 as a first pass, requesting
a commit before further changes. This does not establish completion of every
browser check below or explicit confirmation of the resize fix. Agent browser
automation reports `ERR_BLOCKED_BY_CLIENT` for both `127.0.0.1:8189` and
`localhost:8189`. The three-node example remains unchanged.

| Check | Actual evidence |
| --- | --- |
| Python | 71 passed, including all 54 earlier tests, geometry/landmark/fractional-HU tests, registry bounds/expiry, and an actual aiohttp test server. Same 58 upstream scikit-image deprecation warnings. Endpoint test requires loopback socket permission. |
| Frontend | `npm run typecheck`, `npm test`: 16 passed across pure logic and jsdom interaction tests; `npm run build` produces one 16.18 kB ES module. Canvas drawing is mocked in jsdom, so these are not visual tests. |
| Host | Same revision `95539f56344958339e39b7582a476267d489b0ee`; Python 3.13.13, PyTorch 2.11.0, NumPy 2.4.4, aiohttp 3.13.5, frontend 1.53.6. No host dependency changes. |
| Registration | Real `/extensions` advertises `/extensions/comfyui-dicom-volume/viewer.js`; fetched bundle matches the local build byte-for-byte. Public app/api shims and DOM-widget source maps inspected. |
| Exact planes | Real queued sample: axial indices 0/74/147, coronal 0/256/511, sagittal 0/256/511 all byte-identical to pure extraction. Axial payloads 1,048,576 bytes; others 303,104 bytes. |
| HTTP errors | Bad axis/index/query: 400; unknown and evicted handles: 410. Host rejects mismatched Origin with 403; no broad CORS added. Synthetic aiohttp tests also cover malformed handles and encoded path attempts. |
| Cache recovery | Real graph exceeding eight registry entries evicts the sample handle. An ordinary unchanged sample graph run produces a new handle, and the following run caches normally. No graph-cache patch or dummy input. |
| Multiple loaders/files | Two sample loaders share a usable source generation. Touching only a synthetic source file changes the fingerprint and refreshes its handle. |
| Reconnected client | Real WebSocket client receives both `execution_cached` and `executed` with the sample descriptor on an unchanged graph. This exercises the installed host's UI replay, not a mocked event. |
| Cold restart | Restarted only the isolated host. Prior report's handle returns 410; sample execution, exact planes, lifecycle checks and cached WebSocket replay pass again. Saved-workflow browser restart remains unverified. |
| Mesh regression | Existing `verify_mesh.py` passes against the viewer-enabled host: 224,036 vertices, 447,879 triangles, 10,752,552-byte GLB; exact positions/indices, finite unit normals and established metre dimensions preserved. `cmp` also confirms a byte-identical GLB to Part Two's cold-restart artifact. |
| Local evidence | Ignored `artifacts/slice-verification/check-2/report.json`, `check-3/report.json`, and `mesh/report.json`/`sample.glb`, with sample attribution. Initial incomplete attempts are not counted as passes. |

Test input is an isolated local copy of the existing public sample plus nine tiny
synthetic CT stacks. No data downloads occurred. Separate input/output/temp/user
directories were used. The first launch unexpectedly triggered ComfyUI's legacy
database migration; its original database was renamed back to its original path
without replacing its inode or contents. Later launches used an explicit isolated
`--database-url`. The existing port 8188 process was not stopped. Test hosts were
stopped after verification. Host source and its pre-existing pyproject change
were preserved; the Task 4 planning files were also preserved.

### Reproduce Slice Integration

From the extension checkout, first prepare a new ignored test input directory:

```sh
COMFY_ROOT="/path/to/ComfyUI"
TEST_ROOT="$PWD/artifacts/slice-check"
.venv/bin/python scripts/verify_slices.py --input "$TEST_ROOT/input" --prepare-from "$COMFY_ROOT/input/tcia-med-lymph-073"
mkdir -p "$TEST_ROOT/output" "$TEST_ROOT/temp" "$TEST_ROOT/user"
```

With a free port and verified host interpreter, run a fresh isolated host:

```sh
"$COMFY_ROOT/.venv/bin/python" "$COMFY_ROOT/main.py" --cpu --disable-api-nodes --listen 127.0.0.1 --port 8189 \
  --disable-all-custom-nodes --whitelist-custom-nodes comfyui-dicom-volume --disable-metadata \
  --input-directory "$TEST_ROOT/input" --output-directory "$TEST_ROOT/output" \
  --temp-directory "$TEST_ROOT/temp" --user-directory "$TEST_ROOT/user" \
  --database-url "sqlite:///$TEST_ROOT/user/isolated.db"
```

In another terminal in the extension checkout, run:

```sh
.venv/bin/python scripts/verify_slices.py --input artifacts/slice-check/input --output artifacts/slice-check/check-1
```

Stop only that test host, relaunch it with the same command, and repeat with
`--output artifacts/slice-check/check-2 --previous-report artifacts/slice-check/check-1/report.json`.
The script queues graphs, checks exact bytes and WebSocket cache replay, exercises
eviction, and touches only a prepared synthetic fixture. Stop the test host when
finished. Use separate new output directories for subsequent runs.

### Remaining Browser Checks

A subsequent pair of user screenshots shows full-width layout after refresh and
contraction after selecting the node. Installed frontend source identifies the
side panel's `WidgetLegacy.vue` assigning its width to the shared widget instance.
The viewer now uses `hideInPanel: true`, as core preview widgets do, so selection
does not mount that second renderer. The user confirmed the fix works and that
slice scrubbing is very good, then requested a commit. Typecheck, all 16 frontend
tests, and rebuild pass (16.52 kB bundle). This establishes user acceptance of the
selection-width fix and scrubbing, not completion of every check listed below.

Follow-up: a user screenshot shows the viewer rendering in the loader, but at a
narrow width inside an enlarged node. The frontend now synchronizes widget width
through the host's `afterResize` hook and explicitly fills its CSS container.
C/W fields also have descriptive HU tooltips. Typecheck, all 16 frontend tests,
and rebuild passed (16.41 kB bundle). The later selection-width fix and user
confirmation above supersede that initial resizing check.

1. Restart your own host and refresh its page. Import the unchanged
   `example_workflows/dicom_to_mesh.json`, then Run. Confirm the loader canvas,
   summary, connections and core SaveGLB preview all appear.
2. Inspect first/middle/last slices in all three stored planes. Scrub and rapidly
   switch planes; confirm selection/readout agree. Resize the node and switch
   host light/dark themes; check aspect, letterboxing and readable controls.
3. Change C/W, presets and right/Shift-drag windowing. Check HU at the cursor and
   its absence in the margins. With browser Network open, window changes should
   issue no slice requests, and viewer controls should issue no `/prompt` requests.
   Under throttling, the final selected plane must win over late responses.
4. Add a second loader, run it, and delete it. Confirm the first remains usable.
   Save a workflow with changed axis/index/window settings; refresh, reopen and
   run. Repeat after a host restart. Confirm settings restore and pixels return.
5. Record observed results and explicit acceptance or issues. These observations
   are still needed; automated geometry and DOM checks do not replace them.

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
