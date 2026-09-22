# Manual Integration and Acceptance

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
