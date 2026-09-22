# Sample Data Attribution

## Download the Example Series

After completing the extension's dependency installation in [README.md](README.md),
open another terminal in the extension checkout. Set the absolute path to your
ComfyUI checkout, then run:

```sh
COMFY_ROOT="/absolute/path/to/ComfyUI"
"$COMFY_ROOT/.venv/bin/python" scripts/fetch_sample.py --input-root "$COMFY_ROOT/input"
```

`--input-root` is required. For a host launched with a custom input directory,
use that directory instead. The directory must already exist. The command downloads
one public series (148 slices, about 78 MB uncompressed) into
`input/tcia-med-lymph-073`, verifies its metadata and ZIP contents, and writes
`provenance.json` and the archive's `LICENSE` alongside it. An existing destination
is never overwritten. Refresh ComfyUI after the download, then open the example
workflow and select `tcia-med-lymph-073`.

The sample is optional if you already have supported conventional CT data.
Retain the attribution and usage terms below with sample-derived output.

## Attribution and Terms

Source: [TCIA CT Lymph Nodes](https://www.cancerimagingarchive.net/collection/ct-lymph-nodes/).
Public de-identified case: `MED_LYMPH_073`.
SeriesInstanceUID: `61.7.338133024060269626651520600539598241004`.
Expected images: 148. Published source size: 77,759,514 bytes.

Roth, H., Lu, L., Seff, A., Cherry, K. M., Hoffman, J., Wang, S., Liu, J.,
Turkbey, E., & Summers, R. M. (2015). A new 2.5 D representation for lymph node
detection in CT [Data set]. The Cancer Imaging Archive.
https://doi.org/10.7937/K9/TCIA.2015.AQIIDCNM

Image data: [Creative Commons Attribution 3.0 Unported](https://creativecommons.org/licenses/by/3.0/).
This permits redistribution and adaptation, including commercial use, subject to
attribution and license terms. The code's MIT license does not license this data.

Follow the [TCIA Data Usage Policy](https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/).
Retain the full citation and DOI, license, and policy links with derived data,
verification images, screenshots and presentations. Acknowledge TCIA and this
dataset in oral and written presentations. Describe transformations (for example,
windowing or display resizing) when sharing derivatives. Do not attempt to identify
or contact participants or generate identifying representations. Require downstream
users to preserve these obligations.

The current [DAC guidance](https://wiki.cancerimagingarchive.net/pages/viewpage.action?pageId=22515655)
asks developers of tools providing direct TCIA access to contact its helpdesk for
listing and attribution review. The downloader here fetches one public series by
UID and is not an authentication step.

## Retrieval Provenance

On 2026-09-22, the collection's image-download table and the public NBIA v4
`getSeries` result both listed CC BY 3.0 and the requested series metadata above.
The [current official API guide](https://www.cancerimagingarchive.net/tcia-api-guides/)
links the [NBIA v4 specification](https://cbiit.github.io/NBIA-TCIA/nbia-api.yaml).
It documents `getImage` as a complete-series ZIP retrieval by SeriesInstanceUID.

`scripts/fetch_sample.py` rechecks metadata, fetches only that series, checks HTTP
length when supplied, checks ZIP CRCs, rejects unsafe paths/links and duplicate
filenames, and requires both the expected DICOM file count and DICOM byte total.
The archive's optional root `LICENSE` file is preserved and checksummed separately;
it is not counted as an image or included in the published DICOM byte total.
It records SHA256 for the archive and each extracted file. These SHA256 values
are computed locally, **not publisher-provided integrity hashes**. No publisher
hash comparison is claimed. The script saves provenance next to the sample.

NBIA is transitioning toward IDC, and support for older API versions is scheduled
to end in October 2026. This script uses the documented v4 endpoint. If it stops
working, consult the official guide; do not substitute annotation ZIPs or download
the entire collection. No DICOM files or generated images belong in Git.

Automated diagnostic download and geometry checks passed on 2026-09-22: 148
DICOM files, 77,759,514 DICOM bytes, and a separate 2,793-byte `LICENSE` file.
The volume is float32 with shape `(148, 512, 512)`, spacing
`(0.8515625, 0.8515625, 5.0)` mm and HU range `[-1024, 3071]`; the independently
read middle source plane matched exactly. A run inside ComfyUI produced the same
results.
