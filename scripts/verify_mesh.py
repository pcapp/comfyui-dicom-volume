"""Local host adapter, queued sample export and binary GLB geometry checks."""

import argparse
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from loader import Volume, load_volume
from meshing import gltf_coordinates, volume_to_mesh


def read_glb(data):
    """Read the core exporter's packed POSITION/NORMAL/index accessors."""
    magic, version, length = struct.unpack_from("<4sII", data)
    assert magic == b"glTF" and version == 2 and length == len(data)
    json_length, chunk_type = struct.unpack_from("<II", data, 12)
    assert chunk_type == 0x4E4F534A
    document = json.loads(data[20:20 + json_length])
    offset = 20 + json_length
    bin_length, chunk_type = struct.unpack_from("<II", data, offset)
    assert chunk_type == 0x004E4942
    binary = data[offset + 8:offset + 8 + bin_length]
    for node in document["nodes"]:
        assert not any(key in node for key in ("matrix", "translation", "rotation", "scale"))
    primitive = document["meshes"][0]["primitives"][0]

    def accessor(index):
        entry = document["accessors"][index]
        view = document["bufferViews"][entry["bufferView"]]
        assert "byteStride" not in view and "sparse" not in entry
        dtype = {5126: "<f4", 5125: "<u4", 5123: "<u2"}[entry["componentType"]]
        width = {"VEC3": 3, "SCALAR": 1}[entry["type"]]
        start = view.get("byteOffset", 0) + entry.get("byteOffset", 0)
        values = np.frombuffer(binary, dtype=dtype, count=entry["count"] * width, offset=start)
        return values.reshape(-1, width)

    return (accessor(primitive["attributes"]["POSITION"]),
            accessor(primitive["indices"]).reshape(-1, 3),
            accessor(primitive["attributes"]["NORMAL"]))


def compare_glb(data, vertices, faces, normals):
    actual_vertices, actual_faces, actual_normals = read_glb(data)
    np.testing.assert_array_equal(actual_vertices, vertices)
    np.testing.assert_array_equal(actual_faces, faces)
    np.testing.assert_allclose(actual_normals, normals, atol=1e-6)
    assert np.isfinite(actual_vertices).all() and np.isfinite(actual_normals).all()
    assert actual_faces.min() >= 0 and actual_faces.max() < len(vertices)
    np.testing.assert_allclose(np.linalg.norm(actual_normals, axis=1), 1, atol=1e-5)
    return {"vertices": len(vertices), "triangles": len(faces), "bytes": len(data),
            "bounds_gltf_m": [vertices.min(0).tolist(), vertices.max(0).tolist()],
            "extents_m": np.ptp(vertices, axis=0).tolist(), "exact_position_index_match": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-root", type=Path, required=True)
    parser.add_argument("--server", default="http://127.0.0.1:8189")
    parser.add_argument("--directory", default="tcia-med-lymph-073")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/mesh-check")
    options = parser.parse_args()
    if urlparse(options.server).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Use a local ComfyUI server.")
    options.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(options.host_root.resolve()))
    # Host imports use the verified host interpreter; no diffusion/GPU is needed.
    sys.argv = [sys.argv[0]]
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    import torch
    from comfy_extras.nodes_save_3d import mesh_item_to_glb_bytes

    spec = importlib.util.spec_from_file_location("dicom_extension", ROOT / "__init__.py",
                                                submodule_search_locations=[str(ROOT)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    from dicom_extension.nodes import VolumeToMesh

    z, y, x = np.indices((17, 17, 17))
    hu = (1000 - 100 * np.sqrt((x-8)**2 + (y-8)**2 + (z-8)**2)).astype(np.float32)
    volume = Volume(hu, (0.7, 1.2, 2.5), (12, -23, 45), tuple(np.eye(3).ravel()), "", ())
    mesh = VolumeToMesh.execute(volume, 400, 2).result[0]
    assert mesh.vertices.dtype == mesh.normals.dtype == torch.float32
    assert mesh.faces.dtype == torch.int64
    assert mesh.vertices.shape[0] == mesh.faces.shape[0] == 1
    expected, faces, normals = volume_to_mesh(volume, 400, 2)
    expected, normals = gltf_coordinates(expected, normals)
    synthetic = compare_glb(mesh_item_to_glb_bytes(mesh, 0), expected, faces, normals)
    triangle = expected[faces].astype(float)
    center = expected.mean(0)
    assert np.all(np.einsum("ij,ij->i", np.cross(triangle[:, 1]-triangle[:, 0],
                  triangle[:, 2]-triangle[:, 0]), triangle.mean(1)-center) > 0)

    def request(path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        with urlopen(Request(options.server.rstrip("/") + path, data=data,
                             headers={"Content-Type": "application/json"}), timeout=60) as response:
            return response.read()

    workflow = json.loads((ROOT / "example_workflows/dicom_to_mesh.json").read_text())
    workflow["1"]["inputs"]["directory"] = options.directory
    result = json.loads(request("/prompt", {"prompt": workflow}))
    assert not result.get("node_errors"), result
    prompt_id = result["prompt_id"]
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        history = json.loads(request("/history/" + prompt_id))
        if prompt_id in history:
            break
        time.sleep(0.5)
    else:
        raise TimeoutError("ComfyUI did not finish the mesh workflow within 180 seconds.")
    record = history[prompt_id]
    assert record["status"]["status_str"] == "success", record["status"]
    file_info = record["outputs"]["3"]["3d"][0]
    data = request("/view?" + urlencode(file_info))
    volume = load_volume(options.host_root / "input", options.directory)
    vertices, faces, normals = volume_to_mesh(volume)
    lps_bounds = [vertices.min(0).tolist(), vertices.max(0).tolist()]
    vertices, normals = gltf_coordinates(vertices, normals)
    sample = compare_glb(data, vertices, faces, normals)
    sample["bounds_lps_mm"] = lps_bounds
    sample["threshold_hu"] = 200
    sample["step_size"] = 2
    (options.output / "sample.glb").write_bytes(data)
    (options.output / "ATTRIBUTION.md").write_text(
        (ROOT / "SAMPLE_DATA.md").read_text() +
        "\nMesh derivative: marching cubes at 200 HU, step 2; LPS mm mapped to (-L,S,P) metres.\n")
    report = {"synthetic_adapter_export": synthetic, "sample_queued_export": sample,
              "host_status": "success", "preview_payload": file_info,
              "human_acceptance": "PENDING: mesh inspection and restart observations"}
    (options.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
