"""ComfyUI V3 node registration."""

import logging

import folder_paths
import torch
from comfy_api.latest import ComfyExtension, io, ui

from .loader import discover_directories, load_volume, manifest_fingerprint
from .meshing import gltf_coordinates, volume_to_mesh


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


class VolumeToMesh(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="DICOMVolume_ToMesh",
            display_name="Volume to Mesh",
            category="dicom",
            inputs=[io.Custom("VOLUME").Input("volume"),
                    io.Float.Input("threshold_hu", default=200.0, step=1.0),
                    io.Int.Input("step_size", default=2, min=1)],
            outputs=[io.Mesh.Output(display_name="mesh")],
        )

    @classmethod
    def execute(cls, volume, threshold_hu=200.0, step_size=2):
        vertices, faces, normals = volume_to_mesh(volume, threshold_hu, step_size)
        vertices, normals = gltf_coordinates(vertices, normals)
        mesh = io.Mesh.Type(torch.from_numpy(vertices).unsqueeze(0),
                            torch.from_numpy(faces).unsqueeze(0),
                            normals=torch.from_numpy(normals).unsqueeze(0))
        return io.NodeOutput(mesh)


class DICOMVolumeExtension(ComfyExtension):
    async def get_node_list(self):
        return [LoadDICOMVolume, VolumeToMesh]
