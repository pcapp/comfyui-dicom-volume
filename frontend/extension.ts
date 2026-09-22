import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import type { Descriptor } from "./model";
import { Viewer } from "./viewer";

export interface HostNode {
  comfyClass: string;
  properties: Record<string, unknown>;
  size: [number, number];
  setSize(size: [number, number]): void;
  addDOMWidget(name: string, type: string, root: HTMLElement, options: {
    serialize: boolean; getMinHeight(): number; hideOnZoom: boolean; hideInPanel: boolean;
    afterResize(this: { width?: number }, node: HostNode): void;
  }): { serialize: boolean; width?: number };
  onExecuted?: (output: { dicom_volume?: Descriptor[]; text?: string[] }) => void;
  onConfigure?: (...args: unknown[]) => void;
  onRemoved?: (...args: unknown[]) => void;
}
app.registerExtension({
  name: "dicom-volume.slice-viewer",
  nodeCreated(node: HostNode) {
    if (node.comfyClass !== "DICOMVolume_Load") return;
    const viewer = new Viewer((url, options) => api.fetchApi(url, options), settings => {
      node.properties.dicom_viewer = settings;
    });
    const widget = node.addDOMWidget("dicom_slice_viewer", "dicom_slice_viewer", viewer.root,
      {
        // The side panel's legacy renderer otherwise overwrites this widget's width.
        serialize: false, getMinHeight: () => 370, hideOnZoom: false, hideInPanel: true,
        afterResize(node) { this.width = node.size[0]; },
      });
    widget.serialize = false;
    const executed = node.onExecuted;
    node.onExecuted = function (output) {
      executed?.call(this, output);
      if (output.dicom_volume?.[0]) viewer.output(output.dicom_volume[0], output.text?.join("\n") ?? "");
    };
    const configure = node.onConfigure;
    node.onConfigure = function (...args) { configure?.apply(this, args); viewer.restore(this.properties.dicom_viewer); };
    const removed = node.onRemoved;
    node.onRemoved = function (...args) { viewer.dispose(); removed?.apply(this, args); };
    node.setSize([Math.max(360, node.size[0]), Math.max(470, node.size[1])]);
  },
});
