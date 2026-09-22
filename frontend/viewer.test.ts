// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Viewer } from "./viewer";
import type { Descriptor, Settings } from "./model";

const plane = { width: 3, height: 2, count: 4, spacing: [2, 5] as [number, number], axes: [1, 0, 2] as [number, number, number], flip_x: false, flip_y: true, right_lps: [1, 0, 0], down_lps: [0, 0, -1] };
const descriptor: Descriptor = { handle: "a".repeat(48), dtype: "float32", byte_order: "little", planes: { axial: { ...plane, flip_y: false }, coronal: plane, sagittal: plane } };
const context = { createImageData: (w: number, h: number) => ({ data: new Uint8ClampedArray(w * h * 4) }), putImageData: vi.fn(), scale: vi.fn(), translate: vi.fn(), drawImage: vi.fn() };
const disconnect = vi.fn();
let viewer: Viewer;
let saved: Settings;
let calls: string[];
beforeEach(() => {
  vi.useFakeTimers(); calls = [];
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect = disconnect; });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => context as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, "getBoundingClientRect").mockReturnValue({ left: 0, top: 0, width: 120, height: 100 } as DOMRect);
  viewer = new Viewer(async url => {
    calls.push(url);
    const buffer = new ArrayBuffer(24); const view = new DataView(buffer);
    [0.25, 1.5, 2.75, 100.25, 101.5, 102.75].forEach((v, i) => view.setFloat32(i * 4, v, true));
    return new Response(buffer, { headers: { "X-Slice-Width": "3", "X-Slice-Height": "2", "X-Slice-Dtype": "float32-le" } });
  }, settings => { saved = settings; });
  document.body.append(viewer.root);
});
afterEach(() => { viewer.dispose(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); document.body.innerHTML = ""; });
const input = (name: string) => viewer.root.querySelector<HTMLInputElement>(`[aria-label="${name}"]`)!;
const click = (name: string) => [...viewer.root.querySelectorAll("button")].find(b => b.textContent === name)!.click();
it("restores settings, coalesces scrubbing, and clamps for a new volume", async () => {
  viewer.restore({ axis: "coronal", index: 99, center: 0.25, width: 2.5, handle: "must not persist" });
  viewer.output(descriptor, "Summary");
  input("Slice index").value = "1"; input("Slice index").dispatchEvent(new Event("input"));
  click("Sagittal"); click("Axial");
  await vi.advanceTimersByTimeAsync(40);
  expect(calls).toEqual([`/dicom-volume/slice/${descriptor.handle}/axial/1`]);
  expect(saved).toEqual({ axis: "axial", index: 1, center: 0.25, width: 2.5 });
  viewer.output({ ...descriptor, planes: { ...descriptor.planes, axial: { ...plane, count: 1 } } }, "New");
  expect(input("Slice index").value).toBe("0");
});
it("windows locally, reads original fractional HU, clears outside image", async () => {
  viewer.output(descriptor, "Summary"); await vi.advanceTimersByTimeAsync(40);
  input("Window center").value = "1000"; input("Window center").dispatchEvent(new Event("change"));
  input("Window width").value = "0"; input("Window width").dispatchEvent(new Event("change"));
  expect(input("Window width").value).toBe("400");
  const select = viewer.root.querySelector("select")!; select.value = "Bone"; select.dispatchEvent(new Event("change"));
  expect(saved.center).toBe(400); expect(saved.width).toBe(1800);
  const canvas = viewer.root.querySelector("canvas")!;
  canvas.dispatchEvent(new MouseEvent("pointermove", { clientX: 40, clientY: 25 }));
  expect(viewer.root.querySelector(".dv-hu")!.textContent).toBe("HU: 0.25");
  canvas.dispatchEvent(new MouseEvent("pointermove", { clientX: 10, clientY: 25 }));
  expect(viewer.root.querySelector(".dv-hu")!.textContent).toBe("HU: --");
  expect(calls).toHaveLength(1);
});
it("wheel stays in the widget and disposal cancels pending work/listeners", async () => {
  viewer.output(descriptor, "Summary"); await vi.advanceTimersByTimeAsync(40);
  const canvas = viewer.root.querySelector("canvas")!;
  const parentWheel = vi.fn(); viewer.root.addEventListener("wheel", parentWheel);
  const wheel = new WheelEvent("wheel", { deltaY: 1, bubbles: true, cancelable: true }); canvas.dispatchEvent(wheel);
  expect(wheel.defaultPrevented).toBe(true); expect(parentWheel).not.toHaveBeenCalled();
  viewer.dispose(); await vi.advanceTimersByTimeAsync(40);
  expect(calls).toHaveLength(1); expect(disconnect).toHaveBeenCalled(); expect(document.body.contains(viewer.root)).toBe(false);
});
it("expired state does not queue a graph or leave a previous image visible", async () => {
  viewer.dispose();
  viewer = new Viewer(async () => new Response("", { status: 410 }), () => {});
  viewer.output(descriptor, ""); await vi.advanceTimersByTimeAsync(40);
  expect(viewer.root.querySelector(".dv-status")!.textContent).toContain("Run the graph again");
});
