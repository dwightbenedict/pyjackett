// Status filter dropdown whose options carry the card's coloured dots.
import { h } from "./dom.js";
import { symbol } from "./icons.js";

const dot = (kind) => h("i", { class: `dot status-dot ${kind}`.trim() });

function optionRow([value, text, kind], onPick) {
  return h(
    "button",
    {
      class: "status-option",
      type: "button",
      role: "option",
      onclick: () => onPick(value),
    },
    kind === undefined ? null : dot(kind),
    text,
  );
}

/**
 * Toggle label that is as wide as the longest of `texts`, so the dropdown
 * fits its widest value; an invisible copy of every text sets the width.
 */
export function sizedLabel(text, texts) {
  const sizer = h(
    "span",
    { class: "status-sizer", "aria-hidden": "true" },
    texts.map((t) => h("span", {}, t)),
  );
  return h("span", { class: "status-label" }, h("span", {}, text), sizer);
}

/**
 * Build the dropdown; `options` is [[value, label, dotKind], ...]. Unless
 * `withAll` is false, a first row named `label` clears the filter.
 */
export function statusFilter(
  label,
  options,
  filters,
  key,
  onChange,
  withAll = true,
) {
  const rows = withAll ? [["", label], ...options] : options;
  const current = () => rows.find(([value]) => value === filters[key]);
  const toggle = h("button", {
    class: "status-toggle",
    type: "button",
    "aria-label": label,
    "aria-haspopup": "listbox",
  });
  const menu = h("div", {
    class: "status-menu",
    role: "listbox",
    hidden: true,
  });
  const root = h("div", { class: "status-filter" }, toggle, menu);
  const outside = (event) => !root.contains(event.target) && setOpen(false);
  const setOpen = (open) => {
    menu.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    const listen = open ? "addEventListener" : "removeEventListener";
    document[listen]("mousedown", outside);
  };
  const show = () => {
    const [, text, kind] = current();
    toggle.replaceChildren(
      ...(kind === undefined ? [] : [dot(kind)]),
      sizedLabel(
        text,
        rows.map(([, label]) => label),
      ),
      h(
        "span",
        { class: "status-chevron" },
        symbol("chevron.up.chevron.down", 14, 2.2),
      ),
    );
  };
  const pick = (value) => {
    filters[key] = value;
    setOpen(false);
    show();
    onChange();
  };
  menu.append(...rows.map((row) => optionRow(row, pick)));
  toggle.addEventListener("click", () => setOpen(menu.hidden));
  root.addEventListener(
    "keydown",
    (event) => event.key === "Escape" && setOpen(false),
  );
  show();
  return root;
}
