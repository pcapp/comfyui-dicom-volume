import { app as E } from "../../scripts/app.js";
import { api as _ } from "../../scripts/api.js";
const y = (s, t, e = []) => {
  const n = document.createElementNS("http://www.w3.org/2000/svg", s);
  return Object.keys(t).forEach((o) => {
    n.setAttribute(o, String(t[o]));
  }), e.length && e.forEach((o) => {
    const r = y(...o);
    n.appendChild(r);
  }), n;
};
var R = ([s, t, e]) => y(s, t, e);
const w = {
  xmlns: "http://www.w3.org/2000/svg",
  width: 24,
  height: 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  "stroke-width": 2,
  "stroke-linecap": "round",
  "stroke-linejoin": "round"
};
const k = ["svg", w, [["path", { d: "m15 18-6-6 6-6" }]]];
const z = ["svg", w, [["path", { d: "m9 18 6-6-6-6" }]]];
const A = [
  "svg",
  w,
  [
    ["path", { d: "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" }],
    ["path", { d: "M3 3v5h5" }]
  ]
], C = ["axial", "coronal", "sagittal"], m = {
  "Soft tissue": { center: 40, width: 400 },
  Bone: { center: 400, width: 1800 },
  Lung: { center: -600, width: 1500 }
}, S = { axis: "axial", index: 0, ...m["Soft tissue"] };
function x(s, t) {
  return Number.isFinite(s) && Number.isFinite(t) && t > 0;
}
function L(s) {
  const t = s && typeof s == "object" ? s : {};
  return {
    axis: C.includes(t.axis) ? t.axis : S.axis,
    index: Number.isSafeInteger(t.index) && t.index >= 0 ? t.index : 0,
    ...x(t.center, t.width) ? { center: t.center, width: t.width } : m["Soft tissue"]
  };
}
function B(s, t) {
  return Math.max(0, Math.min(t - 1, Math.round(s)));
}
function P(s, t, e) {
  if (!x(t, e)) throw new Error("Window width must be positive and finite.");
  return Math.round(Math.max(0, Math.min(1, (s - t) / e + 0.5)) * 255);
}
function M(s, t, e) {
  const n = s.width * s.spacing[0], o = s.height * s.spacing[1], r = Math.min(t / n, e / o);
  return { x: (t - n * r) / 2, y: (e - o * r) / 2, width: n * r, height: o * r };
}
function W(s, t, e, n, o) {
  const r = M(s, t, e);
  if (r.width <= 0 || r.height <= 0 || n < r.x || o < r.y || n >= r.x + r.width || o >= r.y + r.height) return null;
  const a = Math.floor((n - r.x) * s.width / r.width), d = Math.floor((o - r.y) * s.height / r.height);
  return { column: s.flip_x ? s.width - 1 - a : a, row: s.flip_y ? s.height - 1 - d : d };
}
function b(s) {
  const t = [["L", "R"], ["P", "A"], ["S", "I"]];
  return s.map((e, n) => ({ v: e, i: n })).filter(({ v: e }) => Math.abs(e) > 0.01).sort((e, n) => Math.abs(n.v) - Math.abs(e.v)).map(({ v: e, i: n }) => t[n][e < 0 ? 1 : 0]).join("");
}
class $ {
  constructor(t = 12, e = 32 * 1024 * 1024) {
    this.maxCount = t, this.maxBytes = e;
  }
  maxCount;
  maxBytes;
  entries = /* @__PURE__ */ new Map();
  get bytes() {
    return [...this.entries.values()].reduce((t, e) => t + e.byteLength, 0);
  }
  get size() {
    return this.entries.size;
  }
  get(t) {
    const e = this.entries.get(t);
    return e && (this.entries.delete(t), this.entries.set(t, e)), e;
  }
  put(t, e) {
    if (this.entries.delete(t), !(e.byteLength > this.maxBytes))
      for (this.entries.set(t, e); this.entries.size > this.maxCount || this.bytes > this.maxBytes; ) this.entries.delete(this.entries.keys().next().value);
  }
  clear() {
    this.entries.clear();
  }
}
class I extends Error {
  constructor(t, e) {
    super(e), this.status = t;
  }
  status;
}
class N {
  constructor(t) {
    this.fetch = t;
  }
  fetch;
  cache = new $();
  generation = 0;
  controller;
  cancel() {
    this.generation++, this.controller?.abort();
  }
  reset() {
    this.cancel(), this.cache.clear();
  }
  async select(t, e, n) {
    this.cancel();
    const o = this.generation, r = `${t.handle}/${e}/${n}`, a = this.cache.get(r);
    if (a) return a;
    this.controller = new AbortController();
    try {
      const d = await this.fetch(`/dicom-volume/slice/${r}`, { signal: this.controller.signal, cache: "no-store" });
      if (o !== this.generation) return;
      if (!d.ok) throw new I(d.status, d.status === 410 ? "Volume expired. Run the graph again." : `Slice request failed (${d.status}).`);
      const v = await d.arrayBuffer();
      if (o !== this.generation) return;
      const g = t.planes[e];
      if (v.byteLength !== g.width * g.height * 4 || d.headers.get("X-Slice-Dtype") !== "float32-le" || Number(d.headers.get("X-Slice-Width")) !== g.width || Number(d.headers.get("X-Slice-Height")) !== g.height) throw new Error("Invalid slice response.");
      const p = new DataView(v), i = new Float32Array(v.byteLength / 4);
      for (let h = 0; h < i.length; h++) i[h] = p.getFloat32(h * 4, !0);
      return this.cache.put(r, i), i;
    } catch (d) {
      if (o !== this.generation) return;
      throw d;
    }
  }
}
const H = ".dicom-viewer{box-sizing:border-box;width:100%;height:100%;min-width:0;display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:auto auto minmax(150px,1fr) auto auto;gap:7px;padding:8px;color:var(--input-text, #ddd);background:var(--comfy-menu-bg, #252525);font:12px sans-serif;letter-spacing:0;overflow:hidden}.dicom-viewer *{box-sizing:border-box;min-width:0}.dicom-viewer .dv-row{display:flex;align-items:center;gap:5px}.dicom-viewer .dv-planes{display:grid;grid-template-columns:repeat(3,1fr);gap:0}.dicom-viewer button,.dicom-viewer select,.dicom-viewer input[type=number]{color:inherit;background:var(--comfy-input-bg, #333);border:1px solid var(--border-color, #666);border-radius:3px;height:27px;font:inherit}.dicom-viewer button{cursor:pointer;padding:3px 5px}.dicom-viewer button[aria-pressed=true]{color:var(--comfy-menu-bg, #222);background:var(--input-text, #ddd)}.dicom-viewer button:focus-visible,.dicom-viewer input:focus-visible,.dicom-viewer select:focus-visible{outline:2px solid var(--p-primary-color, #26a69a);outline-offset:1px}.dicom-viewer .dv-icon{flex:0 0 27px;width:27px;display:grid;place-items:center}.dicom-viewer label{display:flex;align-items:center;gap:4px;flex:1}.dicom-viewer input[type=number]{width:100%;padding:3px}.dicom-viewer input[type=range]{flex:1;width:0}.dicom-viewer select{width:93px}.dicom-viewer .dv-stage{position:relative;min-height:150px;background:#080808;overflow:hidden}.dicom-viewer canvas{position:absolute;width:100%;height:100%;display:block;touch-action:none}.dicom-viewer .dv-status{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:16px;color:#eee;text-align:center;pointer-events:none}.dicom-viewer .dv-status:empty{display:none}.dicom-viewer .dv-orientation{font-size:11px;overflow-wrap:anywhere}.dicom-viewer .dv-count{flex:0 0 72px;text-align:right;font-variant-numeric:tabular-nums}.dicom-viewer .dv-hu{margin-left:auto;font-variant-numeric:tabular-nums;white-space:nowrap}.dicom-viewer .dv-summary{overflow:auto;max-height:36px;font-size:10px;overflow-wrap:anywhere}";
function c(s, t = "", e = "") {
  const n = document.createElement(s);
  return n.className = t, n.textContent = e, n;
}
class q {
  constructor(t, e) {
    if (this.persist = e, this.requests = new N(t), !document.getElementById("dicom-volume-style")) {
      const i = c("style");
      i.id = "dicom-volume-style", i.textContent = H, document.head.append(i);
    }
    const n = c("div", "dv-planes");
    for (const i of C) {
      const h = c("button", "", i[0].toUpperCase() + i.slice(1));
      h.title = `Stored ${i} plane; no anatomical resampling`, this.on(h, "click", () => {
        this.settings.axis = i, this.changedSlice();
      }), n.append(h), this.planeButtons.set(i, h);
    }
    const o = c("div", "dv-row");
    for (const [i, h] of [[this.center, "C"], [this.width, "W"]]) {
      i.type = "number", i.step = "any", i.setAttribute("aria-label", h === "C" ? "Window center" : "Window width"), i.title = h === "C" ? "Window center (HU)" : "Window width (HU)", h === "W" && (i.min = "0.001");
      const u = c("label", "", h);
      u.title = i.title, u.append(i), o.append(u), this.on(i, "change", () => {
        const l = this.center.valueAsNumber, f = this.width.valueAsNumber;
        x(l, f) && (this.settings.center = l, this.settings.width = f, this.save(), this.renderPixels()), this.syncControls();
      });
    }
    const r = c("select");
    r.setAttribute("aria-label", "Window preset"), r.append(new Option("Window...", ""));
    for (const i of Object.keys(m)) r.append(new Option(i, i));
    this.on(r, "change", () => {
      const i = m[r.value];
      i && (Object.assign(this.settings, i), this.save(), this.syncControls(), this.renderPixels()), r.value = "";
    }), o.append(r), this.stage.append(this.canvas, this.status);
    const a = c("div", "dv-row"), d = (i, h, u) => {
      const l = c("button", "dv-icon");
      return l.title = i, l.setAttribute("aria-label", i), l.append(R([h[0], { ...h[1], width: 16, height: 16 }, h[2]])), this.on(l, "click", u), l;
    };
    this.slider.type = "range", this.slider.min = "0", this.slider.max = "0", this.slider.step = "1", this.slider.setAttribute("aria-label", "Slice index"), this.on(this.slider, "input", () => {
      this.settings.index = this.slider.valueAsNumber, this.changedSlice();
    }), a.append(
      d("Previous slice", k, () => this.step(-1)),
      this.slider,
      d("Next slice", z, () => this.step(1)),
      this.count,
      d("Retry slice", A, () => {
        this.requests.reset(), this.changedSlice();
      })
    );
    const v = c("div"), g = c("div", "dv-row");
    g.append(this.orientation, this.hu), v.append(g, this.summary), this.root.append(n, o, this.stage, a, v);
    for (const i of ["pointerdown", "pointermove", "pointerup", "dblclick", "keydown"]) this.on(this.root, i, (h) => h.stopPropagation());
    this.on(this.canvas, "contextmenu", (i) => i.preventDefault()), this.canvas.addEventListener("wheel", (i) => {
      i.preventDefault(), i.stopPropagation(), i.deltaY && this.step(i.deltaY > 0 ? 1 : -1);
    }, { passive: !1, signal: this.events.signal });
    let p;
    this.canvas.addEventListener("pointerdown", (i) => {
      (i.button === 2 || i.shiftKey) && (i.preventDefault(), this.canvas.setPointerCapture(i.pointerId), p = { x: i.clientX, y: i.clientY, center: this.settings.center, width: this.settings.width });
    }, { signal: this.events.signal }), this.canvas.addEventListener("pointermove", (i) => {
      p && (this.settings.center = p.center + (i.clientY - p.y) * 2, this.settings.width = Math.max(1e-3, p.width + (i.clientX - p.x) * 4), this.save(), this.syncControls(), this.renderPixels());
      const h = this.canvas.getBoundingClientRect(), u = this.descriptor?.planes[this.settings.axis], l = u && this.pixels && W(u, h.width, h.height, i.clientX - h.left, i.clientY - h.top);
      this.hu.textContent = l && u ? `HU: ${this.pixels[l.row * u.width + l.column]}` : "HU: --";
    }, { signal: this.events.signal });
    for (const i of ["pointerup", "pointercancel", "lostpointercapture"]) this.on(this.canvas, i, () => {
      p = void 0;
    });
    this.on(this.canvas, "pointerleave", () => {
      this.hu.textContent = "HU: --";
    }), this.observer = new ResizeObserver(() => this.draw()), this.observer.observe(this.stage), this.syncControls();
  }
  persist;
  root = c("div", "dicom-viewer");
  settings = { ...S };
  descriptor;
  pixels;
  requests;
  events = new AbortController();
  canvas = c("canvas");
  source = c("canvas");
  stage = c("div", "dv-stage");
  status = c("div", "dv-status", "Run the graph to view slices.");
  slider = c("input");
  center = c("input");
  width = c("input");
  count = c("span", "dv-count", "0 / 0");
  hu = c("span", "dv-hu", "HU: --");
  orientation = c("span", "dv-orientation", "Stored planes");
  summary = c("div", "dv-summary");
  planeButtons = /* @__PURE__ */ new Map();
  observer;
  timer;
  selection = 0;
  disposed = !1;
  on(t, e, n) {
    t.addEventListener(e, n, { signal: this.events.signal });
  }
  restore(t) {
    this.settings = L(t), this.syncControls(), this.descriptor && this.changedSlice();
  }
  output(t, e) {
    this.disposed || (t.handle !== this.descriptor?.handle && this.requests.reset(), this.descriptor = t, this.summary.textContent = e, this.changedSlice());
  }
  save() {
    this.persist({ ...this.settings });
  }
  step(t) {
    this.settings.index += t, this.changedSlice();
  }
  syncControls() {
    const t = this.descriptor?.planes[this.settings.axis];
    t && (this.settings.index = B(this.settings.index, t.count)), this.slider.max = String((t?.count ?? 1) - 1), this.slider.value = String(this.settings.index), this.slider.disabled = !this.descriptor?.handle, this.count.textContent = t ? `${this.settings.index + 1} / ${t.count}` : "0 / 0", this.center.value = String(this.settings.center), this.width.value = String(this.settings.width);
    for (const [e, n] of this.planeButtons) n.setAttribute("aria-pressed", String(this.settings.axis === e));
    this.orientation.textContent = t ? `Stored ${this.settings.axis} | right ${b(t.right_lps)} / down ${b(t.down_lps)}` : "Stored planes";
  }
  changedSlice() {
    clearTimeout(this.timer), this.requests.cancel();
    const t = ++this.selection;
    if (this.syncControls(), this.save(), this.pixels = void 0, this.hu.textContent = "HU: --", this.draw(), !this.descriptor?.handle) {
      this.status.textContent = this.descriptor ? "Viewer limit: volume exceeds 1 GiB." : "Run the graph to view slices.";
      return;
    }
    this.status.textContent = "Loading...", this.timer = setTimeout(async () => {
      try {
        const e = await this.requests.select(this.descriptor, this.settings.axis, this.settings.index);
        if (!e || t !== this.selection || this.disposed) return;
        this.pixels = e, this.status.textContent = "", this.renderPixels();
      } catch (e) {
        if (t !== this.selection || this.disposed) return;
        this.status.textContent = e instanceof Error ? e.message : "Slice unavailable. Retry or run the graph again.";
      }
    }, 35);
  }
  renderPixels() {
    if (!this.pixels || !this.descriptor) return;
    const t = this.descriptor.planes[this.settings.axis];
    this.source.width = t.width, this.source.height = t.height;
    const e = this.source.getContext("2d"), n = e.createImageData(t.width, t.height);
    for (let o = 0; o < this.pixels.length; o++) {
      const r = P(this.pixels[o], this.settings.center, this.settings.width);
      n.data[o * 4] = n.data[o * 4 + 1] = n.data[o * 4 + 2] = r, n.data[o * 4 + 3] = 255;
    }
    e.putImageData(n, 0, 0), this.draw();
  }
  draw() {
    const t = this.stage.clientWidth, e = this.stage.clientHeight, n = window.devicePixelRatio || 1;
    this.canvas.width = Math.round(t * n), this.canvas.height = Math.round(e * n);
    const o = this.canvas.getContext("2d");
    if (!this.pixels || !this.descriptor || !t || !e) return;
    const r = this.descriptor.planes[this.settings.axis], a = M(r, t, e);
    o.scale(n, n), o.imageSmoothingEnabled = !1, o.translate(a.x + (r.flip_x ? a.width : 0), a.y + (r.flip_y ? a.height : 0)), o.scale(r.flip_x ? -1 : 1, r.flip_y ? -1 : 1), o.drawImage(this.source, 0, 0, a.width, a.height);
  }
  dispose() {
    this.disposed = !0, this.selection++, clearTimeout(this.timer), this.requests.reset(), this.events.abort(), this.observer.disconnect(), this.pixels = void 0, this.descriptor = void 0, this.canvas.width = this.canvas.height = this.source.width = this.source.height = 0, this.root.remove();
  }
}
E.registerExtension({
  name: "dicom-volume.slice-viewer",
  nodeCreated(s) {
    if (s.comfyClass !== "DICOMVolume_Load") return;
    const t = new q((a, d) => _.fetchApi(a, d), (a) => {
      s.properties.dicom_viewer = a;
    }), e = s.addDOMWidget(
      "dicom_slice_viewer",
      "dicom_slice_viewer",
      t.root,
      {
        // The side panel's legacy renderer otherwise overwrites this widget's width.
        serialize: !1,
        getMinHeight: () => 370,
        hideOnZoom: !1,
        hideInPanel: !0,
        afterResize(a) {
          this.width = a.size[0];
        }
      }
    );
    e.serialize = !1;
    const n = s.onExecuted;
    s.onExecuted = function(a) {
      n?.call(this, a), a.dicom_volume?.[0] && t.output(a.dicom_volume[0], a.text?.join(`
`) ?? "");
    };
    const o = s.onConfigure;
    s.onConfigure = function(...a) {
      o?.apply(this, a), t.restore(this.properties.dicom_viewer);
    };
    const r = s.onRemoved;
    s.onRemoved = function(...a) {
      t.dispose(), r?.apply(this, a);
    }, s.setSize([Math.max(360, s.size[0]), Math.max(470, s.size[1])]);
  }
});
