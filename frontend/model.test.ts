import { describe, expect, it } from "vitest";
import { clampIndex, cursorPixel, directionLabel, imageRect, intensity, presets, restore, SliceCache, SliceRequests, validWindow } from "./model";
import type { Descriptor, Plane } from "./model";

const plane: Plane = { width: 3, height: 2, count: 4, spacing: [2, 5], axes: [1, 0, 2], flip_x: false, flip_y: true, right_lps: [1, 0, 0], down_lps: [0, 0, -1] };
const descriptor: Descriptor = { handle: "a".repeat(48), dtype: "float32", byte_order: "little", planes: { axial: plane, coronal: plane, sagittal: plane } };
function response(values = [0.25, 1.5, 2.75, 100.25, 101.5, 102.75]) {
  const bytes = new ArrayBuffer(24), view = new DataView(bytes);
  values.forEach((v, i) => view.setFloat32(i * 4, v, true));
  return new Response(bytes, { headers: { "X-Slice-Width": "3", "X-Slice-Height": "2", "X-Slice-Dtype": "float32-le" } });
}
describe("windowing", () => {
  for (const [name, preset] of Object.entries(presets)) it(name, () => {
    expect(intensity(preset.center - preset.width / 2, preset.center, preset.width)).toBe(0);
    expect(intensity(preset.center, preset.center, preset.width)).toBe(128);
    expect(intensity(preset.center + preset.width / 2, preset.center, preset.width)).toBe(255);
  });
  it("rejects nonpositive/nonfinite widths", () => {
    for (const width of [0, -1, NaN, Infinity]) { expect(validWindow(0, width)).toBe(false); expect(() => intensity(0, 0, width)).toThrow(); }
    expect(validWindow(Infinity, 1)).toBe(false); expect(validWindow(0.25, 0.001)).toBe(true);
  });
});
it("physical letterboxing and every asymmetric cursor landmark with flips", () => {
  expect(imageRect(plane, 120, 100)).toEqual({ x: 30, y: 0, width: 60, height: 100 });
  for (const flip_x of [false, true]) for (const flip_y of [false, true]) {
    const p = { ...plane, flip_x, flip_y };
    for (let row = 0; row < 2; row++) for (let col = 0; col < 3; col++) {
      expect(cursorPixel(p, 120, 100, 40 + col * 20, 25 + row * 50)).toEqual({ column: flip_x ? 2 - col : col, row: flip_y ? 1 - row : row });
    }
    for (const [x, y] of [[29, 50], [90, 50], [50, -1], [50, 100]]) expect(cursorPixel(p, 120, 100, x, y)).toBeNull();
  }
  expect(cursorPixel(plane, 0, 0, 0, 0)).toBeNull();
});
it("derives oblique directional labels from LPS", () => {
  expect(directionLabel([0.36, -0.48, 0.8])).toBe("SAL");
  expect(directionLabel([0, 0, -1])).toBe("I");
});
it("restores only settings and clamps a new volume", () => {
  expect(restore({ axis: "sagittal", index: 9, center: 1.25, width: 2.5, handle: "secret" })).toEqual({ axis: "sagittal", index: 9, center: 1.25, width: 2.5 });
  expect(restore({ axis: "bad", index: -1, center: NaN, width: -1 })).toEqual(restore(null));
  expect(clampIndex(9, 3)).toBe(2); expect(clampIndex(-1, 3)).toBe(0);
});
it("bounds recent slice count and bytes with LRU access", () => {
  const cache = new SliceCache(2, 16);
  cache.put("a", new Float32Array(2)); cache.put("b", new Float32Array(2)); cache.get("a");
  cache.put("c", new Float32Array(2)); expect(cache.get("b")).toBeUndefined(); expect(cache.size).toBe(2);
  cache.put("d", new Float32Array(4)); expect(cache.size).toBe(1); expect(cache.bytes).toBe(16);
  cache.put("huge", new Float32Array(5)); expect(cache.bytes).toBe(16); cache.clear(); expect(cache.bytes).toBe(0);
});
it("decodes exact fractional endpoint values and reuses cache", async () => {
  let calls = 0;
  const requests = new SliceRequests(async (url, options) => { calls++; expect(url).toBe(`/dicom-volume/slice/${descriptor.handle}/coronal/1`); expect(options.cache).toBe("no-store"); return response(); });
  expect([...(await requests.select(descriptor, "coronal", 1))!]).toEqual([0.25, 1.5, 2.75, 100.25, 101.5, 102.75]);
  await requests.select(descriptor, "coronal", 1); expect(calls).toBe(1);
});
it("aborts and ignores an older response even when transport ignores abort", async () => {
  const pending: ((r: Response) => void)[] = []; const signals: AbortSignal[] = [];
  const requests = new SliceRequests(async (_url, options) => { signals.push(options.signal!); return new Promise(resolve => pending.push(resolve)); });
  const old = requests.select(descriptor, "axial", 0);
  const recent = requests.select(descriptor, "sagittal", 1);
  expect(signals[0].aborted).toBe(true);
  pending[1](response()); expect(await recent).toBeInstanceOf(Float32Array);
  pending[0](response()); expect(await old).toBeUndefined(); expect(requests.cache.size).toBe(1);
});
it("ignores delayed body completion and disposal", async () => {
  let finish!: (r: ArrayBuffer) => void;
  const r = response(); r.arrayBuffer = () => new Promise(resolve => { finish = resolve; });
  const requests = new SliceRequests(async () => r);
  const pending = requests.select(descriptor, "axial", 0); await Promise.resolve();
  requests.reset(); finish(new ArrayBuffer(24)); expect(await pending).toBeUndefined(); expect(requests.cache.size).toBe(0);
});
it("reports expiration and invalid payloads", async () => {
  await expect(new SliceRequests(async () => new Response("", { status: 410 })).select(descriptor, "axial", 0)).rejects.toThrow("Run the graph again");
  await expect(new SliceRequests(async () => new Response(new ArrayBuffer(2))).select(descriptor, "axial", 0)).rejects.toThrow("Invalid slice response");
});
