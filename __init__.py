"""Load host-specific registration only when ComfyUI requests the extension."""

WEB_DIRECTORY = "./web"


async def comfy_entrypoint():
    from .nodes import DICOMVolumeExtension
    from .slice_routes import register_routes
    from server import PromptServer

    register_routes(PromptServer.instance)
    return DICOMVolumeExtension()
