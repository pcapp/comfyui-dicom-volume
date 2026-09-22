export const axes = ["axial", "coronal", "sagittal"] as const;
export type Axis = typeof axes[number];
export interface Plane {
  width: number; height: number; count: number; spacing: [number, number];
  axes: [number, number, number]; flip_x: boolean; flip_y: boolean;
  right_lps: number[]; down_lps: number[];
}
export interface Descriptor {
  handle: string | null; dtype: "float32"; byte_order: "little";
  planes: Record<Axis, Plane>;
}
export interface Settings { axis: Axis; index: number; center: number; width: number }
export const presets = {
  "Soft tissue": { center: 40, width: 400 },
  Bone: { center: 400, width: 1800 },
  Lung: { center: -600, width: 1500 },
};
export const defaults: Settings = { axis: "axial", index: 0, ...presets["Soft tissue"] };
export function validWindow(center: number, width: number): boolean {
  return Number.isFinite(center) && Number.isFinite(width) && width > 0;
}
export function restore(value: unknown): Settings {
  const s = (value && typeof value === "object" ? value : {}) as Partial<Settings>;
  return {
    axis: axes.includes(s.axis as Axis) ? s.axis! : defaults.axis,
    index: Number.isSafeInteger(s.index) && s.index! >= 0 ? s.index! : 0,
    ...(validWindow(s.center!, s.width!) ? { center: s.center!, width: s.width! } : presets["Soft tissue"]),
  };
}
export function clampIndex(index: number, count: number): number {
  return Math.max(0, Math.min(count - 1, Math.round(index)));
}
export function intensity(hu: number, center: number, width: number): number {
  if (!validWindow(center, width)) throw new Error("Window width must be positive and finite.");
  return Math.round(Math.max(0, Math.min(1, (hu - center) / width + 0.5)) * 255);
}
export function imageRect(plane: Plane, width: number, height: number) {
  const w = plane.width * plane.spacing[0], h = plane.height * plane.spacing[1];
  const scale = Math.min(width / w, height / h);
  return { x: (width - w * scale) / 2, y: (height - h * scale) / 2, width: w * scale, height: h * scale };
}
export function cursorPixel(plane: Plane, width: number, height: number, x: number, y: number) {
  const r = imageRect(plane, width, height);
  if (r.width <= 0 || r.height <= 0 || x < r.x || y < r.y || x >= r.x + r.width || y >= r.y + r.height) return null;
  const col = Math.floor((x - r.x) * plane.width / r.width);
  const row = Math.floor((y - r.y) * plane.height / r.height);
  return { column: plane.flip_x ? plane.width - 1 - col : col, row: plane.flip_y ? plane.height - 1 - row : row };
}
export function directionLabel(vector: number[]): string {
  const labels = [["L", "R"], ["P", "A"], ["S", "I"]];
  return vector.map((v, i) => ({ v, i })).filter(({ v }) => Math.abs(v) > 0.01)
    .sort((a, b) => Math.abs(b.v) - Math.abs(a.v))
    .map(({ v, i }) => labels[i][v < 0 ? 1 : 0]).join("");
}
export class SliceCache {
  private entries = new Map<string, Float32Array>();
  constructor(readonly maxCount = 12, readonly maxBytes = 32 * 1024 * 1024) {}
  get bytes(): number { return [...this.entries.values()].reduce((n, v) => n + v.byteLength, 0); }
  get size(): number { return this.entries.size; }
  get(key: string) {
    const value = this.entries.get(key);
    if (value) { this.entries.delete(key); this.entries.set(key, value); }
    return value;
  }
  put(key: string, value: Float32Array) {
    this.entries.delete(key);
    if (value.byteLength > this.maxBytes) return;
    this.entries.set(key, value);
    while (this.entries.size > this.maxCount || this.bytes > this.maxBytes) this.entries.delete(this.entries.keys().next().value!);
  }
  clear() { this.entries.clear(); }
}
export class SliceError extends Error {
  constructor(readonly status: number, message: string) { super(message); }
}
export type FetchSlice = (url: string, options: RequestInit) => Promise<Response>;
export class SliceRequests {
  readonly cache = new SliceCache();
  private generation = 0;
  private controller?: AbortController;
  constructor(private fetch: FetchSlice) {}
  cancel() { this.generation++; this.controller?.abort(); }
  reset() { this.cancel(); this.cache.clear(); }
  async select(descriptor: Descriptor, axis: Axis, index: number): Promise<Float32Array | undefined> {
    this.cancel();
    const generation = this.generation;
    const key = `${descriptor.handle}/${axis}/${index}`;
    const cached = this.cache.get(key);
    if (cached) return cached;
    this.controller = new AbortController();
    try {
      const response = await this.fetch(`/dicom-volume/slice/${key}`, { signal: this.controller.signal, cache: "no-store" });
      if (generation !== this.generation) return;
      if (!response.ok) throw new SliceError(response.status, response.status === 410 ? "Volume expired. Run the graph again." : `Slice request failed (${response.status}).`);
      const buffer = await response.arrayBuffer();
      if (generation !== this.generation) return;
      const plane = descriptor.planes[axis];
      if (buffer.byteLength !== plane.width * plane.height * 4 ||
          response.headers.get("X-Slice-Dtype") !== "float32-le" ||
          Number(response.headers.get("X-Slice-Width")) !== plane.width ||
          Number(response.headers.get("X-Slice-Height")) !== plane.height) throw new Error("Invalid slice response.");
      // DataView explicitly decodes little-endian, including on a big-endian client.
      const view = new DataView(buffer), pixels = new Float32Array(buffer.byteLength / 4);
      for (let i = 0; i < pixels.length; i++) pixels[i] = view.getFloat32(i * 4, true);
      this.cache.put(key, pixels);
      return pixels;
    } catch (error) {
      if (generation !== this.generation) return;
      throw error;
    }
  }
}
