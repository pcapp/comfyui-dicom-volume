from pathlib import Path
import stat
import zipfile

import pytest

from scripts import fetch_sample


def archive_fixture(tmp_path, monkeypatch, entries):
    archive = tmp_path / "series.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name, data in entries:
            output.writestr(name, data)
    monkeypatch.setattr(fetch_sample, "EXPECTED_COUNT", len(entries))
    monkeypatch.setattr(fetch_sample, "EXPECTED_BYTES", sum(len(data) for _, data in entries))
    destination = tmp_path / "extracted"
    destination.mkdir()
    return archive, destination


def test_complete_archive(tmp_path, monkeypatch):
    data = b"\x00" * 128 + b"DICM" + b"test"
    archive, destination = archive_fixture(tmp_path, monkeypatch, [("nested/one.dcm", data)])
    records = fetch_sample.extract_series(archive, destination)
    assert (destination / "one.dcm").read_bytes() == data
    assert records[0]["bytes"] == len(data)
    assert len(records[0]["sha256_local"]) == 64


def test_archive_preserves_license_outside_dicom_totals(tmp_path, monkeypatch):
    data = b"\x00" * 128 + b"DICM" + b"test"
    license_text = b"Dataset license and attribution"
    archive, destination = archive_fixture(
        tmp_path, monkeypatch, [("LICENSE", license_text), ("one.dcm", data)])
    monkeypatch.setattr(fetch_sample, "EXPECTED_COUNT", 1)
    monkeypatch.setattr(fetch_sample, "EXPECTED_BYTES", len(data))
    records = fetch_sample.extract_series(archive, destination)
    assert (destination / "LICENSE").read_bytes() == license_text
    assert [record["file"] for record in records] == ["one.dcm"]
    assert (destination / "one.dcm").read_bytes() == data


def test_dicom_size_mismatch_still_rejected(tmp_path, monkeypatch):
    archive, destination = archive_fixture(
        tmp_path, monkeypatch, [("one.dcm", b"\x00" * 128 + b"DICM")])
    monkeypatch.setattr(fetch_sample, "EXPECTED_BYTES", 133)
    with pytest.raises(ValueError, match="Expected 133 DICOM bytes, received 132"):
        fetch_sample.extract_series(archive, destination)


@pytest.mark.parametrize("name", ["../escape.dcm", "/absolute.dcm", "C:/escape.dcm", "..\\escape.dcm"])
def test_zip_path_escape(tmp_path, monkeypatch, name):
    archive, destination = archive_fixture(tmp_path, monkeypatch, [(name, b"\x00" * 128 + b"DICM")])
    with pytest.raises(ValueError, match="Unsafe"):
        fetch_sample.extract_series(archive, destination)


def test_zip_symlink(tmp_path, monkeypatch):
    entry = zipfile.ZipInfo("link.dcm")
    entry.create_system = 3
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    archive, destination = archive_fixture(tmp_path, monkeypatch, [(entry, b"target")])
    with pytest.raises(ValueError, match="Unsafe"):
        fetch_sample.extract_series(archive, destination)


def test_incomplete_zip(tmp_path, monkeypatch):
    archive, destination = archive_fixture(tmp_path, monkeypatch, [("one.dcm", b"\x00" * 128 + b"DICM")])
    monkeypatch.setattr(fetch_sample, "EXPECTED_COUNT", 2)
    with pytest.raises(ValueError, match="Expected 2"):
        fetch_sample.extract_series(archive, destination)
