import { createElement, ChevronLeft, ChevronRight, RotateCcw } from "lucide";
import { axes, clampIndex, cursorPixel, defaults, directionLabel, imageRect, intensity, presets, restore, SliceRequests, validWindow } from "./model";
import type { Axis, Descriptor, FetchSlice, Settings } from "./model";
import css from "./viewer.css?inline";

function element<K extends keyof HTMLElementTagNameMap>(tag: K, className = "", text = ""): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag); el.className = className; el.textContent = text; return el;
}
export class Viewer {
  readonly root = element("div", "dicom-viewer");
  private settings: Settings = { ...defaults };
  private descriptor?: Descriptor;
  private pixels?: Float32Array;
  private readonly requests: SliceRequests;
  private readonly events = new AbortController();
  private readonly canvas = element("canvas");
  private readonly source = element("canvas");
  private readonly stage = element("div", "dv-stage");
  private readonly status = element("div", "dv-status", "Run the graph to view slices.");
  private readonly slider = element("input");
  private readonly center = element("input");
  private readonly width = element("input");
  private readonly count = element("span", "dv-count", "0 / 0");
  private readonly hu = element("span", "dv-hu", "HU: --");
  private readonly orientation = element("span", "dv-orientation", "Stored planes");
  private readonly summary = element("div", "dv-summary");
  private readonly planeButtons = new Map<Axis, HTMLButtonElement>();
  private readonly observer: ResizeObserver;
  private timer?: ReturnType<typeof setTimeout>;
  private selection = 0;
  private disposed = false;

  constructor(fetch: FetchSlice, private persist: (settings: Settings) => void) {
    this.requests = new SliceRequests(fetch);
    if (!document.getElementById("dicom-volume-style")) {
      const style = element("style"); style.id = "dicom-volume-style"; style.textContent = css; document.head.append(style);
    }
    const planes = element("div", "dv-planes");
    for (const axis of axes) {
      const button = element("button", "", axis[0].toUpperCase() + axis.slice(1));
      button.title = `Stored ${axis} plane; no anatomical resampling`;
      this.on(button, "click", () => { this.settings.axis = axis; this.changedSlice(); });
      planes.append(button); this.planeButtons.set(axis, button);
    }
    const windows = element("div", "dv-row");
    for (const [input, label] of [[this.center, "C"], [this.width, "W"]] as const) {
      input.type = "number"; input.step = "any";
      input.setAttribute("aria-label", label === "C" ? "Window center" : "Window width");
      input.title = label === "C" ? "Window center (HU)" : "Window width (HU)";
      if (label === "W") input.min = "0.001";
      const field = element("label", "", label); field.title = input.title; field.append(input); windows.append(field);
      this.on(input, "change", () => {
        const center = this.center.valueAsNumber, width = this.width.valueAsNumber;
        if (validWindow(center, width)) { this.settings.center = center; this.settings.width = width; this.save(); this.renderPixels(); }
        this.syncControls();
      });
    }
    const preset = element("select"); preset.setAttribute("aria-label", "Window preset");
    preset.append(new Option("Window...", ""));
    for (const name of Object.keys(presets)) preset.append(new Option(name, name));
    this.on(preset, "change", () => {
      const value = presets[preset.value as keyof typeof presets];
      if (value) { Object.assign(this.settings, value); this.save(); this.syncControls(); this.renderPixels(); }
      preset.value = "";
    });
    windows.append(preset);
    this.stage.append(this.canvas, this.status);
    const navigation = element("div", "dv-row");
    const button = (title: string, icon: typeof ChevronLeft, action: () => void) => {
      const el = element("button", "dv-icon"); el.title = title; el.setAttribute("aria-label", title);
      el.append(createElement([icon[0], { ...icon[1], width: 16, height: 16 }, icon[2]])); this.on(el, "click", action); return el;
    };
    this.slider.type = "range"; this.slider.min = "0"; this.slider.max = "0"; this.slider.step = "1";
    this.slider.setAttribute("aria-label", "Slice index");
    this.on(this.slider, "input", () => { this.settings.index = this.slider.valueAsNumber; this.changedSlice(); });
    navigation.append(button("Previous slice", ChevronLeft, () => this.step(-1)), this.slider,
      button("Next slice", ChevronRight, () => this.step(1)), this.count,
      button("Retry slice", RotateCcw, () => { this.requests.reset(); this.changedSlice(); }));
    const footer = element("div");
    const readouts = element("div", "dv-row"); readouts.append(this.orientation, this.hu);
    footer.append(readouts, this.summary);
    this.root.append(planes, windows, this.stage, navigation, footer);
    for (const event of ["pointerdown", "pointermove", "pointerup", "dblclick", "keydown"]) this.on(this.root, event, e => e.stopPropagation());
    this.on(this.canvas, "contextmenu", e => e.preventDefault());
    this.canvas.addEventListener("wheel", e => { e.preventDefault(); e.stopPropagation(); if (e.deltaY) this.step(e.deltaY > 0 ? 1 : -1); }, { passive: false, signal: this.events.signal });
    let drag: { x: number; y: number; center: number; width: number } | undefined;
    this.canvas.addEventListener("pointerdown", e => {
      if (e.button === 2 || e.shiftKey) {
        e.preventDefault(); this.canvas.setPointerCapture(e.pointerId);
        drag = { x: e.clientX, y: e.clientY, center: this.settings.center, width: this.settings.width };
      }
    }, { signal: this.events.signal });
    this.canvas.addEventListener("pointermove", e => {
      if (drag) {
        this.settings.center = drag.center + (e.clientY - drag.y) * 2;
        this.settings.width = Math.max(0.001, drag.width + (e.clientX - drag.x) * 4);
        this.save(); this.syncControls(); this.renderPixels();
      }
      const rect = this.canvas.getBoundingClientRect();
      const plane = this.descriptor?.planes[this.settings.axis];
      const p = plane && this.pixels && cursorPixel(plane, rect.width, rect.height, e.clientX - rect.left, e.clientY - rect.top);
      this.hu.textContent = p && plane ? `HU: ${this.pixels![p.row * plane.width + p.column]}` : "HU: --";
    }, { signal: this.events.signal });
    for (const event of ["pointerup", "pointercancel", "lostpointercapture"]) this.on(this.canvas, event, () => { drag = undefined; });
    this.on(this.canvas, "pointerleave", () => { this.hu.textContent = "HU: --"; });
    this.observer = new ResizeObserver(() => this.draw()); this.observer.observe(this.stage);
    this.syncControls();
  }
  private on(target: EventTarget, event: string, handler: (event: Event) => void) {
    target.addEventListener(event, handler, { signal: this.events.signal });
  }
  restore(value: unknown) { this.settings = restore(value); this.syncControls(); if (this.descriptor) this.changedSlice(); }
  output(descriptor: Descriptor, summary: string) {
    if (this.disposed) return;
    if (descriptor.handle !== this.descriptor?.handle) this.requests.reset();
    this.descriptor = descriptor; this.summary.textContent = summary;
    this.changedSlice();
  }
  private save() { this.persist({ ...this.settings }); }
  private step(delta: number) { this.settings.index += delta; this.changedSlice(); }
  private syncControls() {
    const plane = this.descriptor?.planes[this.settings.axis];
    if (plane) this.settings.index = clampIndex(this.settings.index, plane.count);
    this.slider.max = String((plane?.count ?? 1) - 1); this.slider.value = String(this.settings.index);
    this.slider.disabled = !this.descriptor?.handle;
    this.count.textContent = plane ? `${this.settings.index + 1} / ${plane.count}` : "0 / 0";
    this.center.value = String(this.settings.center); this.width.value = String(this.settings.width);
    for (const [axis, button] of this.planeButtons) button.setAttribute("aria-pressed", String(this.settings.axis === axis));
    this.orientation.textContent = plane ? `Stored ${this.settings.axis} | right ${directionLabel(plane.right_lps)} / down ${directionLabel(plane.down_lps)}` : "Stored planes";
  }
  private changedSlice() {
    clearTimeout(this.timer); this.requests.cancel(); const selection = ++this.selection;
    this.syncControls(); this.save(); this.pixels = undefined; this.hu.textContent = "HU: --"; this.draw();
    if (!this.descriptor?.handle) {
      this.status.textContent = this.descriptor ? "Viewer limit: volume exceeds 1 GiB." : "Run the graph to view slices.";
      return;
    }
    this.status.textContent = "Loading...";
    this.timer = setTimeout(async () => {
      try {
        const pixels = await this.requests.select(this.descriptor!, this.settings.axis, this.settings.index);
        if (!pixels || selection !== this.selection || this.disposed) return;
        this.pixels = pixels; this.status.textContent = ""; this.renderPixels();
      } catch (error) {
        if (selection !== this.selection || this.disposed) return;
        this.status.textContent = error instanceof Error ? error.message : "Slice unavailable. Retry or run the graph again.";
      }
    }, 35);
  }
  private renderPixels() {
    if (!this.pixels || !this.descriptor) return;
    const plane = this.descriptor.planes[this.settings.axis];
    this.source.width = plane.width; this.source.height = plane.height;
    const ctx = this.source.getContext("2d")!;
    const image = ctx.createImageData(plane.width, plane.height);
    for (let i = 0; i < this.pixels.length; i++) {
      const value = intensity(this.pixels[i], this.settings.center, this.settings.width);
      image.data[i * 4] = image.data[i * 4 + 1] = image.data[i * 4 + 2] = value; image.data[i * 4 + 3] = 255;
    }
    ctx.putImageData(image, 0, 0); this.draw();
  }
  private draw() {
    const width = this.stage.clientWidth, height = this.stage.clientHeight;
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.round(width * dpr); this.canvas.height = Math.round(height * dpr);
    const ctx = this.canvas.getContext("2d")!;
    if (!this.pixels || !this.descriptor || !width || !height) return;
    const plane = this.descriptor.planes[this.settings.axis], rect = imageRect(plane, width, height);
    ctx.scale(dpr, dpr); ctx.imageSmoothingEnabled = false;
    ctx.translate(rect.x + (plane.flip_x ? rect.width : 0), rect.y + (plane.flip_y ? rect.height : 0));
    ctx.scale(plane.flip_x ? -1 : 1, plane.flip_y ? -1 : 1);
    ctx.drawImage(this.source, 0, 0, rect.width, rect.height);
  }
  dispose() {
    this.disposed = true; this.selection++; clearTimeout(this.timer); this.requests.reset();
    this.events.abort(); this.observer.disconnect(); this.pixels = undefined; this.descriptor = undefined;
    this.canvas.width = this.canvas.height = this.source.width = this.source.height = 0;
    this.root.remove();
  }
}
