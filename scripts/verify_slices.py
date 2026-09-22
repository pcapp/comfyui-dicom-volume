"""Prepare isolated input or verify slice routes/cache on an already running local host."""

import argparse
import asyncio
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from loader import load_volume
from slices import extract_slice


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--prepare-from", type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8189")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--previous-report", type=Path)
    options = parser.parse_args()
    if options.prepare_from:
        options.input.mkdir(parents=True, exist_ok=False)
        shutil.copytree(options.prepare_from, options.input / "tcia-med-lymph-073")
        # Small conventional oblique CT fixtures; never download data.
        import SimpleITK as sitk
        for n in range(9):
            directory = options.input / f"synthetic-{n}"
            directory.mkdir()
            for z in range(3):
                pixels = (np.arange(20).reshape(4, 5) + z * 100).astype(np.int16)
                image = sitk.GetImageFromArray(pixels)
                image.SetSpacing((0.7, 1.2))
                tags = {"0008|0016": "1.2.840.10008.5.1.4.1.1.2", "0008|0060": "CT",
                        "0008|0018": f"1.2.826.0.1.3680043.10.543.{n+1}.{z+1}",
                        "0020|000d": "1.2.826.0.1.3680043.10.543.999",
                        "0020|000e": f"1.2.826.0.1.3680043.10.543.{n+1}",
                        "0020|0032": f"12\\-23\\{45+z*2.5}",
                        "0020|0037": "0.8\\0.6\\0\\-0.6\\0.8\\0",
                        "0028|0030": "1.2\\0.7", "0028|1052": "0", "0028|1053": "1", "0028|1054": "HU"}
                for key, value in tags.items(): image.SetMetaData(key, value)
                writer = sitk.ImageFileWriter(); writer.KeepOriginalImageUIDOn(); writer.SetImageIO("GDCMImageIO")
                writer.SetFileName(str(directory / f"slice-{z}")); writer.Execute(image)
        (options.input.parent / "ATTRIBUTION.md").write_text((ROOT / "SAMPLE_DATA.md").read_text())
        print("Prepared existing public sample copy and nine synthetic stacks.")
        return
    if urlparse(options.server).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Use a local host.")
    if options.output is None: parser.error("--output is required for verification.")
    options.output.mkdir(parents=True, exist_ok=False)

    def request(path, payload=None, headers=None):
        data = json.dumps(payload).encode() if payload is not None else None
        return urlopen(Request(options.server + path, data=data,
                       headers={"Content-Type": "application/json", **(headers or {})}), timeout=30)

    def queue(graph, client_id=None):
        with request("/prompt", {"prompt": graph, "client_id": client_id}) as response:
            submitted = json.load(response)
        assert not submitted.get("node_errors"), submitted
        prompt_id = submitted["prompt_id"]
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            with request("/history/" + prompt_id) as response: history = json.load(response)
            if prompt_id in history:
                record = history[prompt_id]
                assert record["status"]["status_str"] == "success", record["status"]
                return record
            time.sleep(0.2)
        raise TimeoutError("Host did not finish.")

    def handle(record, node="1"):
        return record["outputs"][node]["dicom_volume"][0]["handle"]

    def cached(record):
        return [node for kind, info in record["status"]["messages"]
                if kind == "execution_cached" for node in info["nodes"]]

    if options.previous_report:
        old = json.loads(options.previous_report.read_text())["sample_handle"]
        try: request(f"/dicom-volume/slice/{old}/axial/0")
        except HTTPError as error: assert error.code == 410
        else: raise AssertionError("Pre-restart handle still live")

    graph = {"1": {"class_type": "DICOMVolume_Load", "inputs": {"directory": "tcia-med-lymph-073"}}}
    first = queue(graph); token = handle(first)
    second = queue(graph)
    assert handle(second) == token and "1" in cached(second), second["status"]

    async def cached_websocket():
        from aiohttp import ClientSession
        client_id = str(uuid.uuid4())
        async with ClientSession() as session:
            async with session.ws_connect(options.server + "/ws?clientId=" + client_id) as ws:
                queued = asyncio.create_task(asyncio.to_thread(queue, graph, client_id))
                received = []
                try:
                    async with asyncio.timeout(30):
                        while True:
                            event = await ws.receive_json()
                            received.append(event)
                            if event["type"] == "execution_success": break
                finally:
                    await queued
                assert any(e["type"] == "execution_cached" and "1" in e["data"]["nodes"] for e in received)
                assert any(e["type"] == "executed" and e["data"]["output"].get("dicom_volume", [{}])[0].get("handle") == token for e in received)
    asyncio.run(cached_websocket())
    volume = load_volume(options.input, "tcia-med-lymph-073")
    checked = []
    descriptor = first["outputs"]["1"]["dicom_volume"][0]
    for axis, plane in descriptor["planes"].items():
        for index in (0, plane["count"] // 2, plane["count"] - 1):
            with request(f"/dicom-volume/slice/{token}/{axis}/{index}") as response:
                data = response.read()
                assert response.headers["X-Slice-Dtype"] == "float32-le"
                assert response.headers["Cache-Control"] == "no-store"
                assert data == extract_slice(volume, axis, index).tobytes()
            checked.append([axis, index, len(data)])
    errors = []
    for tail, status in [(f"{token}/axial/999", 400), (f"{token}/bad/0", 400),
                         (f"{token}/axial/-1", 400), (f"{token}/axial/0?path=/etc/passwd", 400),
                         ("0"*48 + "/axial/0", 410)]:
        try: request("/dicom-volume/slice/" + tail)
        except HTTPError as error: assert error.code == status; errors.append(status)
        else: raise AssertionError("Invalid request accepted")
    try: request(f"/dicom-volume/slice/{token}/axial/0", headers={"Origin": "https://example.org"})
    except HTTPError as error: assert error.code == 403
    else: raise AssertionError("Host origin protection bypassed")

    # Keep node 1 in the graph while >8 other references evict its HTTP handle.
    crowded = dict(graph)
    for n in range(9):
        crowded[str(n+2)] = {"class_type": "DICOMVolume_Load", "inputs": {"directory": f"synthetic-{n}"}}
    evicted = queue(crowded); expired = handle(evicted)
    try: request(f"/dicom-volume/slice/{expired}/axial/0")
    except HTTPError as error: assert error.code == 410
    else: raise AssertionError("Expected bounded registry eviction")
    recovered = queue(graph)
    assert handle(recovered) != expired and "1" not in cached(recovered)
    with request(f"/dicom-volume/slice/{handle(recovered)}/axial/0") as response: assert response.status == 200
    stable = queue(graph)
    assert "1" in cached(stable) and handle(stable) == handle(recovered)
    # Two independently placed nodes can share one immutable source generation.
    two = dict(graph); two["11"] = graph["1"]
    multiple = queue(two)
    assert handle(multiple) == handle(multiple, "11")
    synthetic = {"1": {"class_type": "DICOMVolume_Load", "inputs": {"directory": "synthetic-0"}}}
    before = queue(synthetic)
    source = next((options.input / "synthetic-0").iterdir())
    source.touch()
    after = queue(synthetic)
    assert handle(before) != handle(after) and "1" not in cached(after)
    report = {"planes": checked, "bad_request_statuses": errors, "origin_403": True,
              "cache_hit": True, "evicted_410": True, "unchanged_graph_recovered": True,
              "recovered_graph_caches_again": True, "multiple_nodes": True, "file_change": True,
              "cached_executed_websocket_payload": True,
              "old_handle_rejected_after_restart": bool(options.previous_report),
              "sample_handle": handle(queue(graph)), "browser_acceptance": "Not established by this script"}
    (options.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (options.output / "ATTRIBUTION.md").write_text((ROOT / "SAMPLE_DATA.md").read_text())
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
