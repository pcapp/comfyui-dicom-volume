"""Queue the organ example, check GLB exports and selector-only cache reuse."""

import argparse
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import numpy as np
import SimpleITK as sitk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from loader import load_volume
from meshing import gltf_coordinates, mask_to_mesh
from segmentation import Grid, LABELS, Segmentation, restore_labels, select_anatomy
from verify_mesh import compare_glb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8189")
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if urlparse(args.server).hostname not in ("localhost", "127.0.0.1", "::1"):
        parser.error("Use a local host.")
    args.output.mkdir(parents=True, exist_ok=True)

    def request(path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        with urlopen(Request(args.server + path, data=data,
                             headers={"Content-Type": "application/json"}), timeout=60) as response:
            return response.read()

    def queue(graph):
        start = time.monotonic()
        response = json.loads(request("/prompt", {"prompt": graph}))
        assert not response.get("node_errors"), response
        prompt_id = response["prompt_id"]
        while time.monotonic() - start < 1800:
            history = json.loads(request("/history/" + prompt_id))
            if prompt_id in history:
                record = history[prompt_id]
                assert record["status"]["status_str"] == "success", record["status"]
                return record, time.monotonic() - start
            time.sleep(0.5)
        raise TimeoutError("Organ workflow exceeded 30 minutes.")

    workflow = json.loads((ROOT / "example_workflows/dicom_organs.json").read_text())
    record, seconds = queue(workflow)
    volume = load_volume(args.input_root, workflow["1"]["inputs"]["directory"])
    grid = Grid.from_volume(volume)
    segmentation = Segmentation(restore_labels(sitk.ReadImage(str(args.labels)), grid), grid, LABELS, {})
    exports = {}
    for node, anatomy in (("5", "heart"), ("8", "both lungs"), ("11", "aorta")):
        info = record["outputs"][node]["3d"][0]
        data = request("/view?" + urlencode(info))
        vertices, faces, normals = mask_to_mesh(select_anatomy(segmentation, anatomy))
        vertices, normals = gltf_coordinates(vertices, normals)
        exports[anatomy] = compare_glb(data, vertices, faces, normals)
        (args.output / f"{anatomy.replace(' ', '_')}.glb").write_bytes(data)
    workflow["3"]["inputs"]["anatomy"] = "left lung"
    switched, switch_seconds = queue(workflow)
    cached = [node for kind, info in switched["status"]["messages"] if kind == "execution_cached"
              for node in info["nodes"]]
    assert "2" in cached and "3" not in cached, cached
    data = request("/view?" + urlencode(switched["outputs"]["5"]["3d"][0]))
    vertices, faces, normals = mask_to_mesh(select_anatomy(segmentation, "left lung"))
    vertices, normals = gltf_coordinates(vertices, normals)
    switched_export = compare_glb(data, vertices, faces, normals)
    report = dict(seconds=seconds, exports=exports, selector_switch_seconds=switch_seconds,
                  cached_nodes=cached, switched_export=switched_export,
                  status="success", browser_acceptance="not established by this script")
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "ATTRIBUTION.md").write_text((ROOT / "SAMPLE_DATA.md").read_text() +
        "\nTotalSegmentator 2.18.0 standard CT total; Apache-2.0.\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
