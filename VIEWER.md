# Slice Viewer Contract

Not for clinical use. DICOM data and derivatives may be identifying. No telemetry,
uploads, new data downloads or external runtime requests are added.

## Integration

Verified against host revision `95539f56344958339e39b7582a476267d489b0ee`, frontend
1.53.6. `WEB_DIRECTORY` exposes built `web/viewer.js`, importing only the public
`scripts/app.js` and `scripts/api.js` shims. Python registers the HTTP route on
`PromptServer.instance.routes` and adds an aiohttp cleanup context.

The typed DOM widget owns an HTML canvas. Installed source maps show that Vue
component mounting uses internal `ComponentWidgetImpl`, `addWidget`, and frontend
store imports. The supported `addDOMWidget` route avoids private bundles and a
second Vue runtime. `nodeCreated`, chained `onExecuted`/`onConfigure`/`onRemoved`,
DOM widget minimum height, and ResizeObserver cover mounting and cleanup.
`hideInPanel` keeps the stateful viewer on its node: the installed side panel's
legacy widget renderer otherwise writes its narrower width onto the same widget
when the node is selected. This follows the host's own preview-widget convention.
Both the widget's `serialize` flag and option are false. Only sanitized
`dicom_viewer` settings go into node properties; no pixels or handles do.

The V3 node returns its existing `VOLUME`, `text` summary, and a `dicom_volume`
UI descriptor. The installed host replays UI on cache hits via `executed`;
the frontend dispatches it to `onExecuted`. A reconnected client can run an
unchanged graph to receive that payload. The viewer does not auto-queue anything.

References: official [extension registration](https://docs.comfy.org/custom-nodes/js/javascript_overview),
[hooks](https://docs.comfy.org/custom-nodes/js/javascript_hooks), and
[V3 UI dictionaries](https://docs.comfy.org/custom-nodes/v3_migration).
Installed source maps and real-host tests establish the version-specific behavior.

## Geometry and Transport

`GET /dicom-volume/slice/{handle}/{axis}/{index}` returns one unwindowed plane as
row-major IEEE 754 **little-endian float32**, with no prefix or integer truncation.
`X-Slice-Width`, `X-Slice-Height`, and `X-Slice-Dtype: float32-le` identify the
payload; its length is width*height*4. Responses are `application/octet-stream`,
`Cache-Control: no-store`. DataView decoding explicitly selects little-endian.

| Axis | Fixed index | Transport row/column | Width/height spacing | Display |
| --- | --- | --- | --- | --- |
| axial | z | y, x | sx, sy | x increases right; y increases down |
| coronal | y | z, x | sx, sz | x increases right; z increases up |
| sagittal | x | z, y | sy, sz | y increases right; z increases up |

Coronal/sagittal flip vertically only during drawing. Cursor mapping first
removes letterboxing, then reverses display flips before indexing the HU plane.
Tests exhaust every landmark of an asymmetric volume. Physical image aspect is
`(width*s_horizontal)/(height*s_vertical)`. Nearest-neighbor canvas scaling changes
display size, never the voxel array. No anatomical reorientation is performed.

Right/down vectors are signed columns of the DICOM direction matrix. Labels list
components above 0.01 in decreasing magnitude: L/P/S for positive, R/A/I for
negative. Compound labels describe obliquity. Origin stays in the volume affine;
it does not affect pixel spacing or direction labels.

Windowing maps `center-width/2` to black and `center+width/2` to white, linearly
clipped. This is an explicit display convention, not the DICOM VOI-LUT half-unit
convention. Fractional original HU remains available to the cursor. Window changes
make no network requests.

Malformed handles, axes, integer indices, out-of-bounds indices and query
parameters receive 400; unknown/expired valid handles receive 410. Unmatched
routes receive host 404. Requests accept no filesystem paths, filenames or UIDs.
Opaque handles contain 192 random bits. They are transient capabilities within
the host's existing access boundary, not separate authentication. `api.fetchApi`
and normal middleware preserve host auth/origin behavior. No CORS is added.

## Lifetime

The registry holds references to executed volumes, not copies or decoded slices.
An LRU bounds it to eight entries (including reservations) and 1 GiB of voxel
data. Identical source manifests share a generation. Access refreshes a 10-minute
idle deadline. Expired handles fail immediately on lookup; a 30-second cleanup
task releases idle references without traffic. Shutdown cancels that task;
restart discards all handles.

During `fingerprint_inputs`, the source-file digest reserves a random generation.
That pair is ComfyUI's cache fingerprint; execution attaches the volume to the
reservation. After expiry/eviction, reservation produces a different generation,
so an ordinary run reloads and publishes a usable handle. Subsequent runs cache
normally. File changes also change the digest. Over-capacity graphs can evict
each other's previews and reexecute on later runs. Volumes over 1 GiB retain only
a small reservation and display a size-limit message; meshing remains available.

Deleting a frontend node cancels requests, timers, listeners, canvas buffers,
and ResizeObserver. It does not revoke a handle shared by other nodes or tabs.
Idle/LRU limits release that reference. Eviction never modifies a volume retained
by downstream nodes or ComfyUI's own cache.

Each viewer retains at most 12 slices and 32 MiB in its LRU, plus the current
plane and drawing buffers. Scrubbing coalesces for 35 ms, aborts prior fetches,
and checks generations before and after body decoding. Late results cannot
replace a newer selection even if transport ignores cancellation. New handles
reset the cache. Retry clears it; expired recovery requires Run.
