# Task 4: Selectable Organ Segmentation with TotalSegmentator

Status: implemented and accepted by Peter on 2026-09-22; finer-grained
segmentation is deferred to a later pass. Actual checks and remaining limits are recorded
in VERIFICATION.md (Task Four). Setup and usage are in SEGMENTATION.md.
Prepared for Astra6 on 2026-09-22 at Peter's request.

## Outcome

Load a conventional CT volume, segment supported anatomy locally, select one
organ or a group, and preview/export its mesh through the existing ComfyUI
pipeline. The first demonstration should extract the heart, lungs, and aorta
from the existing sample as separately selectable objects. No model training.

This is Task 4. Do not infer completion of earlier tasks or invent Task 3 scope.
Read the current checkout and any applicable AGENTS.md before implementation;
this plan describes a target, not a snapshot that overrides later work.

## Starting Point

- `loader.py`: `Volume` contains float32 HU voxels in `(z,y,x)`, spacing in
  `(x,y,z)`, LPS origin, direction matrix, and source-series provenance.
- `meshing.py`: HU isosurfaces are transformed to physical LPS millimetres;
  `gltf_coordinates` converts to `(-L,S,P)` metres. Retain this convention.
- `nodes.py`: V3 `Load DICOM Volume` and `Volume to Mesh` adapters. Use the
  installed host's MESH and SaveGLB contracts, as verified in Task 2.
- `VERIFICATION.md` and `NOTES.md` contain historical evidence. Some descriptions
  differ from current code; inspect and test the implementation as authority.
- The checkout has existing uncommitted mesh work. Preserve it. Do not reset,
  rebase, commit, publish, or edit ComfyUI core as part of this task.
- Recorded environments: extension Python 3.14.2; host Python 3.13.13. Recheck
  rather than assuming TotalSegmentator dependencies support either environment.

## Scope and Product Decisions

Use TotalSegmentator's standard CT `total` task only for the first delivery.
Start with full segmentation so downstream organ changes reuse the same result.
Offer native-resolution quality and a clearly labeled fast mode where supported.
Keep specialized licensed tasks, MRI, lesions, interactive mask editing, custom
viewers, and multi-material scene export outside Task 4.

Proposed graph:

```text
Load DICOM Volume -> Segment CT Anatomy -> Select Anatomy -> Mask to Mesh -> SaveGLB
                                      -> Select Anatomy -> Mask to Mesh -> SaveGLB
```

Use three small nodes with stable IDs and explicit custom types:

| Node | Inputs | Outputs |
| --- | --- | --- |
| Segment CT Anatomy | VOLUME, quality, device | SEGMENTATION |
| Select Anatomy | SEGMENTATION, named organ/group | VOLUME_MASK |
| Mask to Mesh | VOLUME_MASK, step size | host MESH |

Selection must expose supported individual labels plus useful groups: left lung,
right lung, both lungs, all ribs, and thoracic vertebrae. Groups are unions of
explicit label IDs, never substring matching. Multiple selector branches allow
separate organ exports without rerunning inference. A single group produces a
union mask, not a promise of separately colored objects. Prefer native ComfyUI
combo controls; arbitrary multi-select is optional only if the installed API
supports it cleanly without new frontend infrastructure.

## Execution Sequence

### 1. Verify Backend and Environment

Read the applicable Python tooling skill before Python commands. Inspect host
and extension interpreters, package versions, installed V3 contracts, and current
Git state. Check a pinned released TotalSegmentator version for Python, PyTorch,
nnU-Net, NumPy, and accelerator compatibility before installing anything.

Keep segmentation dependencies optional and imports lazy: loader and HU meshing
must still work without them. Prefer in-process inference if it fits the existing
host. If compatible dependencies require replacing host packages or changing its
interpreter, use a separate supported worker environment and a subprocess adapter
with argument lists, bounded diagnostics, exit checks, and cancellation cleanup.
Do not sync or rebuild the shared host environment. Record the selected approach
and verified versions; do not leave both architectures half implemented.

### 2. Establish Model Setup and License Records

Pin the task, package version, checkpoint identities, label map, and source URLs.
Use a dedicated model cache outside Git. Provide an explicit setup/download step
with size/progress where available; no downloads during node discovery/import.
Missing weights should produce an actionable setup message. After setup,
inference must work without network access. Disable upstream usage telemetry.

Record checkpoint hashes, source, license and applicable notices in a small model
manifest. Validate setup against the pinned backend's expected model files; fail
clearly on incomplete/corrupt downloads. Do not download every upstream task.

Upstream currently lists `total` under Apache-2.0. Recheck the exact selected
release and checkpoint terms. Include required licenses, attribution and NOTICE
content in third-party documentation, including relevant bundled dependencies.
Keep our code MIT. Add requested scientific citations separately. Do not package
restricted heart-chamber/coronary models under the standard task's permission.

### 3. Implement the Geometry-Preserving Adapter

Add a host-independent segmentation module and typed data contracts:

- SEGMENTATION: integer 3D labels, ID-to-name mapping, original grid geometry,
  source identity, and model/version/quality provenance.
- VOLUME_MASK: boolean 3D mask on that same grid, selected names/IDs, geometry,
  and source identity. Do not repurpose HU `Volume` as a label container.

Convert the original HU volume to the backend input without display windowing.
Explicitly handle `(z,y,x)` versus `(x,y,z)` and DICOM LPS versus NIfTI RAS.
Prefer established SimpleITK/nibabel conversions with a tested affine. Let the
backend perform its required preprocessing, then restore predictions onto the
original grid with nearest-neighbor label resampling when needed. Verify shape,
affine, integer values and allowed IDs; matching dimensions alone are insufficient.
Preserve oblique orientations. Never silently discard geometry or interpolate
labels with linear/cubic methods. Do not modify the input volume.

Use ComfyUI's existing graph cache first. Selection changes must not invalidate
the inference node. Include model identity and relevant settings in cache
invalidation so changed weights cannot reuse old predictions. Avoid a second
persistent segmentation cache unless measured need justifies it.

### 4. Implement Selection and Mask Meshing

Build the organ catalog from the pinned task's actual label mapping. Reject
unknown selections and distinguish a valid but absent organ from invalid input.
Return a valid empty mask for an absent structure; meshing should explain that
there is no surface rather than crashing inside marching cubes.

Mesh a binary mask at 0.5, with a detail-preserving default step of 1. Reuse the
existing physical-coordinate and host-MESH logic without changing HU-node behavior.
If zero padding is used to close mask boundaries, compensate the vertex offset;
record when anatomy touches the scan boundary, since a closed mesh does not mean
the entire organ was scanned. Preserve disconnected components by default.
Do not smooth, decimate, fill holes, or discard small components implicitly.

### 5. Add Nodes and a Working Example

Register the three V3 nodes and expose device choices supported by the verified
backend. Prefer MPS on compatible Apple hardware, CUDA where available, and a
documented CPU fallback. Report the actual resolved device; fail clearly on an
explicit unsupported choice. Support host cancellation and release inference
resources after use so the model does not occupy accelerator memory indefinitely.

Provide an example with one inference node and separate heart, lungs, and aorta
branches using core SaveGLB preview/export. Preserve model and sample attribution
alongside generated evidence. Update setup instructions and troubleshooting for
missing dependencies, weights, device memory, and absent/truncated anatomy.

### 6. Verify and Record Evidence

Run offline tests without importing ComfyUI or downloading models:

- Independent coordinate landmarks establish LPS/RAS and axis-order correctness
  for anisotropic, translated, oblique, and reflected grids.
- Simulated backend output on another grid restores discrete labels correctly;
  include same-shape/different-affine cases, invalid IDs, and empty structures.
- Organ groups contain exactly their specified labels; source HU stays unchanged.
- Mask meshes have correct physical bounds, units, winding and finite normals;
  cover boundary padding offsets and disconnected regions.
- Existing loader and HU-meshing tests continue to pass.

Then perform an explicitly recorded real-model integration run on the installed
sample. Its recorded 5 mm slice spacing limits fine anatomy; do not mistake an
upsampled mesh for recovered detail. Record model hashes, device, runtime, memory
where measurable, output labels, nonempty voxel counts, and geometry agreement.
Inspect mask overlays on representative axial/coronal/sagittal slices and the
exported meshes. This sample has no established organ ground truth, so report
visual plausibility and alignment, not a numerical accuracy claim.

Use a free host port without stopping another server. Verify actual browser
workflow loading, organ switching, rotation/zoom, and SaveGLB export. Confirm
selector changes reuse inference, changing model/quality reruns it, and a cold
restart works with network unavailable after setup. Exercise failure and
cancellation paths. Keep automated evidence separate from Peter's observations;
do not invent human acceptance. Retain the project's nonclinical-use scope.

## Completion Criteria and Handoff

Task 4 is implemented when the example runs end to end, each chosen organ can be
independently selected and exported in correct physical alignment, segmentation
is reused across selections, setup is reproducible with pinned licensed weights,
and offline plus real-host verification is recorded. Report any browser or human
acceptance still pending explicitly.

Expected deliverables: backend/geometry adapter, segmentation and mask contracts,
selection catalog, mask meshing, three V3 nodes, focused tests, example workflow,
setup/license documentation, and a Task 4 evidence section in VERIFICATION.md.
Finish with changed-file summary, actual checks/results, performance observations,
and unresolved limitations. No inferred success or unrequested publishing.

## Research References

Revalidate against the pinned release; these links track upstream development.

- Tasks, selected organs, devices, Python API, telemetry and model downloads:
  https://github.com/wasserth/TotalSegmentator
- Standard label mapping:
  https://github.com/wasserth/TotalSegmentator/blob/master/totalsegmentator/map_to_binary.py
- Upstream license:
  https://github.com/wasserth/TotalSegmentator/blob/master/LICENSE
- Apache redistribution conditions:
  https://www.apache.org/licenses/LICENSE-2.0
- Requested TotalSegmentator citation:
  https://doi.org/10.1148/ryai.230024
- nnU-Net implementation and citation:
  https://github.com/MIC-DKFZ/nnUNet
