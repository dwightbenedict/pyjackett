// Icons shown above the tab labels on narrow screens (SF Symbols style).
import { h } from "./dom.js";

const PATHS = {
  indexers:
    '<rect x="3" y="4" width="18" height="7" rx="2.5"/>' +
    '<rect x="3" y="13" width="18" height="7" rx="2.5"/>' +
    '<path d="M7 7.5h.01M7 16.5h.01"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M20 20l-4.9-4.9"/>',
  logs:
    '<path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>' +
    '<path d="M14 3v5h5M9 13h6M9 17h6"/>',
};

export function tabIcon(name) {
  const span = h("span", { class: "tab-icon", "aria-hidden": "true" });
  span.innerHTML =
    '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" ' +
    'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" ' +
    `stroke-linejoin="round">${PATHS[name] ?? ""}</svg>`;
  return span;
}
