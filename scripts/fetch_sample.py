"""Explicitly fetch one public TCIA series; standard library only."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from urllib.parse import urlencode
from urllib.request import urlopen
import zipfile


SERIES_UID = "61.7.338133024060269626651520600539598241004"
CASE_ID = "MED_LYMPH_073"
EXPECTED_COUNT = 148
EXPECTED_BYTES = 77759514
API = "https://nbia.cancerimagingarchive.net/nbia-api/services/v4/"
COLLECTION = "https://www.cancerimagingarchive.net/collection/ct-lymph-nodes/"
LICENSE = "https://creativecommons.org/licenses/by/3.0/"
POLICY = "https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/"
CITATION = (
    "Roth, H., Lu, L., Seff, A., Cherry, K. M., Hoffman, J., Wang, S., Liu, J., "
    "Turkbey, E., & Summers, R. M. (2015). A new 2.5 D representation for lymph node "
    "detection in CT [Data set]. The Cancer Imaging Archive. "
    "https://doi.org/10.7937/K9/TCIA.2015.AQIIDCNM"
)


def extract_series(archive: Path, destination: Path) -> list[dict]:
    """Extract only a complete, bounded series; reject links and unsafe ZIP paths."""
    records = []
    names = set()
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        licenses = [entry for entry in entries if entry.filename == "LICENSE" and not entry.is_dir()]
        if len(licenses) > 1 or any(entry.file_size > 65536 for entry in licenses):
            raise ValueError("Unexpected ZIP LICENSE entries or size.")
        files = [entry for entry in entries if not entry.is_dir() and entry not in licenses]
        observed_bytes = sum(entry.file_size for entry in files)
        if observed_bytes != EXPECTED_BYTES:
            raise ValueError(f"Expected {EXPECTED_BYTES} DICOM bytes, received {observed_bytes}; "
                             "do not use this download.")
        if len(files) != EXPECTED_COUNT:
            raise ValueError(f"Expected {EXPECTED_COUNT} DICOM files, received {len(files)}.")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            mode = entry.external_attr >> 16
            if (path.is_absolute() or ".." in path.parts or "\\" in entry.filename
                    or ":" in entry.filename or stat.S_ISLNK(mode)
                    or (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)))):
                raise ValueError("Unsafe ZIP entry; download was not extracted.")
            if entry.is_dir():
                continue
            # Flatten the single series into one dropdown directory.
            name = path.name
            if name.casefold() in names or name.casefold() == "provenance.json":
                raise ValueError("Duplicate or reserved ZIP filename; download was not extracted.")
            names.add(name.casefold())
            digest = hashlib.sha256()
            with source.open(entry) as incoming, (destination / name).open("xb") as outgoing:
                header = incoming.read(132)
                if entry not in licenses and header[128:132] != b"DICM":
                    raise ValueError("Expected TCIA Part 10 DICOM files; unexpected archive content.")
                outgoing.write(header)
                digest.update(header)
                for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
                    outgoing.write(chunk)
                    digest.update(chunk)
            if entry not in licenses:
                records.append({"file": name, "bytes": entry.file_size,
                                "sha256_local": digest.hexdigest()})
    return sorted(records, key=lambda record: record["file"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("/Users/peter/repos/ComfyUI/input"))
    args = parser.parse_args()
    root = args.input_root.resolve(strict=True)
    destination = root / "tcia-med-lymph-073"
    if destination.exists() or destination.is_symlink():
        parser.error(f"Destination already exists; nothing overwritten: {destination}")
    print(f"TCIA CT Lymph Nodes / {CASE_ID}: {EXPECTED_COUNT} images, ~78 MB source DICOM.")
    print(f"Destination: {destination}\nLicense: {LICENSE}\nPolicy: {POLICY}\n{CITATION}")
    print("Preserve this attribution, license and policy downstream; do not identify or contact participants.")
    metadata_url = API + "getSeries?" + urlencode({"SeriesInstanceUID": SERIES_UID, "format": "json"})
    with urlopen(metadata_url, timeout=60) as response:
        records = json.load(response)
    matching = [record for record in records if record["SeriesInstanceUID"] == SERIES_UID]
    if len(matching) != 1:
        raise ValueError("NBIA did not return exactly the requested series.")
    metadata = matching[0]
    if (metadata["Collection"] != "CT Lymph Nodes" or metadata["PatientID"] != CASE_ID
            or metadata["Modality"] != "CT" or int(metadata["ImageCount"]) != EXPECTED_COUNT
            or int(metadata["FileSize"]) != EXPECTED_BYTES
            or metadata["LicenseURI"].replace("http://", "https://").rstrip("/") != LICENSE.rstrip("/")):
        raise ValueError("Public metadata changed; review the series and license before downloading.")
    url = API + "getImage?" + urlencode({"SeriesInstanceUID": SERIES_UID, "NewFileNames": "No"})
    with tempfile.TemporaryDirectory(prefix=".tcia-download-", dir=root) as temporary:
        temporary = Path(temporary)
        archive = temporary / "series.zip"
        digest = hashlib.sha256()
        transfer_bytes = 0
        with urlopen(url, timeout=120) as response, archive.open("xb") as output:
            expected_transfer = response.headers.get("Content-Length")
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                transfer_bytes += len(chunk)
                if transfer_bytes > 200_000_000:
                    raise ValueError("Download exceeded the single-series size limit.")
                output.write(chunk)
                digest.update(chunk)
        if expected_transfer is not None and transfer_bytes != int(expected_transfer):
            raise ValueError("Incomplete HTTP transfer; rerun the explicit fetch command.")
        stage = temporary / "extracted"
        stage.mkdir()
        files = extract_series(archive, stage)
        provenance = {
            "collection": COLLECTION, "case_id": CASE_ID, "series_uid": SERIES_UID,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "metadata_url": metadata_url, "download_url": url,
            "expected_count": EXPECTED_COUNT, "observed_count": len(files),
            "expected_dicom_bytes": EXPECTED_BYTES, "zip_transfer_bytes": transfer_bytes,
            "zip_sha256_local": digest.hexdigest(), "files": files,
            "integrity": "ZIP CRC checked on extraction; SHA256 values computed locally, not publisher checksums.",
            "publisher_checksums": None, "citation": CITATION, "license": LICENSE, "policy": POLICY,
            "downstream": "Preserve dataset citation, DOI, license and policy; require downstream attribution. "
                          "Acknowledge TCIA in presentations. Do not identify or contact participants.",
        }
        license_file = stage / "LICENSE"
        if license_file.exists():
            provenance["archive_license"] = {
                "file": "LICENSE", "bytes": license_file.stat().st_size,
                "sha256_local": hashlib.sha256(license_file.read_bytes()).hexdigest(),
            }
        (stage / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        destination.mkdir()  # Exclusive creation: never overwrite an existing directory or symlink.
        for path in stage.iterdir():
            shutil.move(str(path), destination / path.name)
    print(f"Verified {len(files)} files and ZIP CRCs. Provenance: {destination / 'provenance.json'}")
    print("Geometry and HU suitability still require verify_volume.py and human review.")


if __name__ == "__main__":
    main()
