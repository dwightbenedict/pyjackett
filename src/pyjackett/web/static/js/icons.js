// SF Symbols-style icons drawn as inline SVG strokes.
import { h } from "./dom.js";

const PATHS = {
  xmark: '<path d="M6 6l12 12M18 6L6 18"/>',
  checkmark: '<path d="M5 12.5l4.5 4.5L19 7"/>',
  "chevron.up": '<path d="M6 15l6-6 6 6"/>',
  "chevron.down": '<path d="M6 9l6 6 6-6"/>',
  "chevron.left": '<path d="M15 6l-6 6 6 6"/>',
  magnifyingglass:
    '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M20 20l-4.9-4.9"/>',
  "arrow.up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
  "arrow.down": '<path d="M12 5v14M6 13l6 6 6-6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6.5V12h4.5"/>',
  externaldrive:
    '<rect x="3" y="5" width="18" height="14" rx="3.5"/>' +
    '<path d="M3 13.5h18"/>' +
    '<circle cx="16.5" cy="16.3" r="0.9" fill="currentColor" stroke="none"/>',
  tray:
    '<path d="M4 13.5l2.2-7a2.5 2.5 0 0 1 2.4-1.7h6.8a2.5 2.5 0 0 1 ' +
    '2.4 1.7l2.2 7v4A2.5 2.5 0 0 1 17.5 20h-11A2.5 2.5 0 0 1 4 17.5z' +
    'M4 13.5h4.5l1 2h5l1-2H20"/>',
  "arrow.up.right": '<path d="M7 17L17 7M8 7h9v9"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  "chevron.up.chevron.down": '<path d="M8 9.5l4-4 4 4M8 14.5l4 4 4-4"/>',
  "arrow.clockwise":
    '<path d="M18.9 8A8 8 0 1 1 14 4.3"/><path d="M13.5 1.2 16.5 4.3 ' +
    '13.5 7.4"/>',
  trash:
    '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 ' +
    '2-2l1-12M9 7V4h6v3"/>',
  ellipsis:
    '<circle cx="5" cy="12" r="1.2" fill="currentColor"/>' +
    '<circle cx="12" cy="12" r="1.2" fill="currentColor"/>' +
    '<circle cx="19" cy="12" r="1.2" fill="currentColor"/>',
  "dot.radiowaves.up.forward":
    '<path d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16"/>' +
    '<circle cx="5" cy="19" r="1"/>',
  "doc.text":
    '<path d="M14 3H8a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3h8a3 3 0 0 0 3-3V8z"/>' +
    '<path d="M14 3v3.5A1.5 1.5 0 0 0 15.5 8H19M8.5 13h7M8.5 16.5h7"/>',
  "doc.on.doc":
    '<rect x="9" y="9" width="11" height="11" rx="2.5"/>' +
    '<path d="M15 9V6.5A2.5 2.5 0 0 0 12.5 4h-6A2.5 2.5 0 0 0 4 6.5v6A2.5 ' +
    '2.5 0 0 0 6.5 15H9"/>',
};

/** Inner SVG markup of a symbol, for swapping into an existing <svg>. */
export function symbolPaths(name) {
  return PATHS[name] ?? "";
}

/** An inline <svg> element for the named symbol. */
export function symbol(name, size = 18, width = 1.8) {
  const wrapper = h("span", { class: "symbol", "aria-hidden": "true" });
  wrapper.innerHTML =
    `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" ` +
    `stroke="currentColor" stroke-width="${width}" stroke-linecap="round" ` +
    `stroke-linejoin="round">${symbolPaths(name)}</svg>`;
  return wrapper;
}

/** A round toolbar button holding only a symbol. */
export function iconButton(name, label, onclick, className = "") {
  return h(
    "button",
    {
      class: `icon-btn ${className}`.trim(),
      type: "button",
      title: label,
      "aria-label": label,
      onclick,
    },
    symbol(name),
  );
}

const SPOKES = 12;

/**
 * Apple activity indicator. The spokes never move: each one fades in turn
 * (see `.spinner line` in app.css), so the indicator stays centred.
 */
export function spinner(size = 18) {
  const spokes = Array.from(
    { length: SPOKES },
    (_, index) =>
      `<line x1="12" y1="2" x2="12" y2="6.5" style="--i:${index}" ` +
      `transform="rotate(${(360 / SPOKES) * index} 12 12)"/>`,
  );
  const element = h("span", {
    class: "spinner",
    role: "progressbar",
    "aria-label": "Loading",
    style: `width:${size}px;height:${size}px`,
  });
  element.innerHTML =
    '<svg viewBox="0 0 24 24" width="100%" height="100%" ' +
    'stroke="currentColor" stroke-width="2.2" stroke-linecap="round">' +
    `${spokes.join("")}</svg>`;
  return element;
}
