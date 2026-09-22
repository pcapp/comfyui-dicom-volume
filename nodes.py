"""ComfyUI V3 node registration."""

import logging

import folder_paths
import torch
from comfy_api.latest import ComfyExtension, io

from .loader import discover_directories, load_volume, manifest_fingerprint
from .meshing import gltf_coordinates, volume_to_mesh, mask_to_mesh
from .segmentation import ANATOMY_OPTIONS, select_anatomy
from .segmentation_backend import QUALITIES, model_fingerprint, segment_volume
from .slice_routes import registry
from .slices import volume_descriptor


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
        fingerprint = manifest_fingerprint(folder_paths.get_input_directory(), directory)
        return fingerprint, registry.reserve(fingerprint)

    @classmethod
    def execute(cls, directory):
        fingerprint = manifest_fingerprint(folder_paths.get_input_directory(), directory)
        volume = load_volume(folder_paths.get_input_directory(), directory)
        summary = volume.summary()
        logging.info("Load DICOM Volume: %s", summary)
        handle = registry.register(fingerprint, volume)
        return io.NodeOutput(volume, ui={"text": [summary], "dicom_volume": [
            volume_descriptor(volume, handle)]})


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


class SegmentCTAnatomy(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="DICOMVolume_SegmentAnatomy", display_name="Segment CT Anatomy", category="dicom",
            inputs=[io.Custom("VOLUME").Input("volume"),
                    io.Combo.Input("quality", options=QUALITIES, default=QUALITIES[1]),
                    io.Combo.Input("device", options=["auto", "mps", "cuda", "cpu"])],
            outputs=[io.Custom("SEGMENTATION").Output(display_name="segmentation")])

    @classmethod
    def fingerprint_inputs(cls, volume, quality, device):
        return model_fingerprint(quality)

    @classmethod
    def execute(cls, volume, quality=QUALITIES[1], device="auto"):
        from comfy.model_management import throw_exception_if_processing_interrupted
        result = segment_volume(volume, quality, device, throw_exception_if_processing_interrupted)
        logging.info("Segment CT Anatomy: %s/%s on %s in %.1fs", result.provenance["model"],
                     quality, result.provenance["device"], result.provenance["seconds"])
        return io.NodeOutput(result)


class SelectAnatomy(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="DICOMVolume_SelectAnatomy", display_name="Select Anatomy", category="dicom",
            inputs=[io.Custom("SEGMENTATION").Input("segmentation"),
                    io.Combo.Input("anatomy", options=ANATOMY_OPTIONS)],
            outputs=[io.Custom("VOLUME_MASK").Output(display_name="mask")])

    @classmethod
    def execute(cls, segmentation, anatomy="heart"):
        return io.NodeOutput(select_anatomy(segmentation, anatomy))


class MaskToMesh(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="DICOMVolume_MaskToMesh", display_name="Mask to Mesh", category="dicom",
            inputs=[io.Custom("VOLUME_MASK").Input("mask"),
                    io.Int.Input("step_size", default=1, min=1)],
            outputs=[io.Mesh.Output(display_name="mesh")])

    @classmethod
    def execute(cls, mask, step_size=1):
        if mask.touches_boundary:
            logging.warning("Selected anatomy touches the scan boundary; the closed mesh may be truncated.")
        vertices, faces, normals = mask_to_mesh(mask, step_size)
        vertices, normals = gltf_coordinates(vertices, normals)
        mesh = io.Mesh.Type(torch.from_numpy(vertices).unsqueeze(0),
                            torch.from_numpy(faces).unsqueeze(0),
                            normals=torch.from_numpy(normals).unsqueeze(0))
        return io.NodeOutput(mesh)


class DICOMVolumeExtension(ComfyExtension):
    async def get_node_list(self):
        return [LoadDICOMVolume, VolumeToMesh, SegmentCTAnatomy, SelectAnatomy, MaskToMesh]
