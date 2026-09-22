"""Local slice transport; registered on the host's existing middleware stack."""

import asyncio
from contextlib import suppress
import re

from aiohttp import web

from .slices import VolumeRegistry, extract_slice, plane_geometry


registry = VolumeRegistry()


def slice_response(store, handle, axis, index):
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if not re.fullmatch(r"[0-9a-f]{48}", handle) or not re.fullmatch(r"0|[1-9][0-9]{0,8}", index):
        return web.Response(status=400, text="Invalid slice request.", headers=headers)
    if axis not in ("axial", "coronal", "sagittal"):
        return web.Response(status=400, text="Invalid axis.", headers=headers)
    try:
        volume = store.get(handle)
    except KeyError:
        return web.Response(status=410, text="Volume expired. Run the graph again.", headers=headers)
    try:
        plane = extract_slice(volume, axis, int(index))
    except ValueError:
        return web.Response(status=400, text="Slice index out of range.", headers=headers)
    geometry = plane_geometry(volume, axis)
    headers.update({"X-Slice-Width": str(geometry["width"]),
                    "X-Slice-Height": str(geometry["height"]),
                    "X-Slice-Dtype": "float32-le"})
    return web.Response(body=plane.tobytes(), content_type="application/octet-stream", headers=headers)


def register_routes(server):
    async def cleanup_context(app):
        async def expire_idle():
            while True:
                await asyncio.sleep(30)
                registry.prune()
        task = asyncio.create_task(expire_idle())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    server.app.cleanup_ctx.append(cleanup_context)

    @server.routes.get("/dicom-volume/slice/{handle}/{axis}/{index}")
    async def get_slice(request):
        if request.query:
            return web.Response(status=400, text="Unexpected parameters.", headers={"Cache-Control": "no-store"})
        return slice_response(registry, **request.match_info)
