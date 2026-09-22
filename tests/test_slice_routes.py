"""Exercise aiohttp with synthetic data, without importing ComfyUI."""
import asyncio
import importlib.util
from pathlib import Path
import sys

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from tests.test_slices import fixture_volume

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dicom_route_test", root / "__init__.py",
                                             submodule_search_locations=[str(root)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from dicom_route_test import slice_routes


def test_actual_aiohttp_route_bytes_errors_and_privacy():
    async def check():
        volume = fixture_volume()
        store = slice_routes.registry
        token = store.register("fixture", volume)
        routes = web.RouteTableDef()
        app = web.Application()
        host = type("Host", (), {"routes": routes, "app": app})()
        slice_routes.register_routes(host)
        app.add_routes(routes)
        async with TestClient(TestServer(app)) as client:
            for axis, expected in [("axial", volume.voxels[1]), ("coronal", volume.voxels[:, 1]),
                                   ("sagittal", volume.voxels[:, :, 1])]:
                response = await client.get(f"/dicom-volume/slice/{token}/{axis}/1")
                assert response.status == 200
                assert response.headers["Cache-Control"] == "no-store"
                assert response.headers["X-Slice-Dtype"] == "float32-le"
                assert int(response.headers["X-Slice-Width"]) == expected.shape[1]
                assert int(response.headers["X-Slice-Height"]) == expected.shape[0]
                assert await response.read() == expected.astype("<f4").tobytes()
                assert "Access-Control-Allow-Origin" not in response.headers
            for tail, status in [(f"{token}/axial/-1", 400), (f"{token}/axial/3", 400),
                                 (f"{token}/bad/0", 400), (f"{token}/axial/1.5", 400),
                                 (f"{token}/axial/00", 400), ("0"*48 + "/axial/0", 410),
                                 (f"{token}/axial/0?path=/etc/passwd", 400),
                                 ("file/axial/0", 400)]:
                response = await client.get("/dicom-volume/slice/" + tail)
                assert response.status == status
                assert "private" not in await response.text()
            response = await client.get("/dicom-volume/slice/%2Fetc%2Fpasswd/axial/0")
            assert response.status in (400, 404)
    asyncio.run(check())
