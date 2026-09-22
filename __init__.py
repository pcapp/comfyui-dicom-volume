"""Load host-specific registration only when ComfyUI requests the extension."""


async def comfy_entrypoint():
    from .nodes import DICOMVolumeExtension

    return DICOMVolumeExtension()
