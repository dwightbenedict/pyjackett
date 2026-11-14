// Dropdown with checkmarked options, styled like the status filter.
import { h } from "./dom.js";
import { symbol } from "./icons.js";
import { sizedLabel } from "./status-filter.js";

function optionRow([value, text], picked, onToggle) {
  const mark = h(
    "span",
    { class: "check-mark" },
    symbol("checkmark", 14, 2.4),
  );
  const row = h(
    "button",
    {
      class: "status-option",
      type: "button",
      role: "option",
      onclick: () => onToggle(value),
    },
    mark,
    text,
  );
  const sync = () => {
    const on = picked.has(value);
    mark.style.visibility = on ? "visible" : "hidden";
    row.setAttribute("aria-selected", String(on));
  };
  sync();
  return { row, sync };
}

/**
 * `options` is [[value, label], ...]. The toggle reads `all` when nothing
 * is picked, the label of a single pick, or "N <noun>" for several.
 */
export function multiFilter({
  all,
  noun,
  options,
  selected = [],
  onChange = () => {},
}) {
  const picked = new Set(selected);
  const labels = new Map();
  const toggle = h("button", {
    class: "status-toggle",
    type: "button",
    "aria-label": all,
    "aria-haspopup": "listbox",
  });
  const menu = h("div", {
    class: "status-menu scroll",
    role: "listbox",
    "aria-multiselectable": "true",
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
  const title = () => {
    if (!picked.size) return all;
    if (picked.size === 1) return labels.get([...picked][0]) ?? all;
    return `${picked.size} ${noun}`;
  };
  const show = () =>
    toggle.replaceChildren(
      sizedLabel(title(), [all, `${labels.size} ${noun}`, ...labels.values()]),
      h(
        "span",
        { class: "status-chevron" },
        symbol("chevron.up.chevron.down", 14, 2.2),
      ),
    );
  let rows = [];
  const toggleValue = (value) => {
    picked.has(value) ? picked.delete(value) : picked.add(value);
    rows.forEach((r) => r.sync());
    show();
    onChange();
  };
  // Picks that the new options no longer offer are dropped.
  const setOptions = (next) => {
    labels.clear();
    next.forEach(([value, text]) => labels.set(value, text));
    [...picked].filter((v) => !labels.has(v)).forEach((v) => picked.delete(v));
    rows = next.map((option) => optionRow(option, picked, toggleValue));
    menu.replaceChildren(...rows.map((r) => r.row));
    show();
  };
  toggle.addEventListener("click", () => setOpen(menu.hidden));
  root.addEventListener(
    "keydown",
    (event) => event.key === "Escape" && setOpen(false),
  );
  // Replace the picks, keeping the given order (the first is the primary).
  const setSelected = (values) => {
    picked.clear();
    values.forEach((value) => picked.add(value));
    rows.forEach((r) => r.sync());
    show();
  };
  setOptions(options);
  return {
    root,
    values: () => [...picked].join(","),
    list: () => [...picked],
    setOptions,
    setSelected,
  };
}
