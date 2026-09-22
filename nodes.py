"""ComfyUI V3 node registration."""

import logging

import folder_paths
from comfy_api.latest import ComfyExtension, io, ui

from .loader import discover_directories, load_volume, manifest_fingerprint


class LoadDICOMVolume(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="DICOMVolume_Load",
            display_name="Load DICOM Volume",
            category="dicom",
            inputs=[io.Combo.Input("directory", options=discover_directories(
                folder_paths.get_input_directory()))],
            outputs=[io.Custom("VOLUME").Output(display_name="volume")],
            is_output_node=True,
        )

    @classmethod
    def fingerprint_inputs(cls, directory):
        return manifest_fingerprint(folder_paths.get_input_directory(), directory)

    @classmethod
    def execute(cls, directory):
        volume = load_volume(folder_paths.get_input_directory(), directory)
        summary = volume.summary()
        logging.info("Load DICOM Volume: %s", summary)
        return io.NodeOutput(volume, ui=ui.PreviewText(summary))


class DICOMVolumeExtension(ComfyExtension):
    async def get_node_list(self):
        return [LoadDICOMVolume]
