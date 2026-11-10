// Renders an indexer configuration (list of typed items) as a form.
import { h } from "./dom.js";

/** Each renderer returns {node, read(item) -> updated item}. */
const RENDERERS = {
  inputstring: (item) => {
    const input = h("input", { type: "text", value: item.value ?? "" });
    return field(item, input, () => ({ ...item, value: input.value }));
  },
  password: (item) => {
    const input = h("input", {
      type: "password",
      value: item.value ?? "",
      autocomplete: "new-password",
    });
    return field(item, input, () => ({ ...item, value: input.value }));
  },
  inputtags: (item) => {
    const input = h("input", { type: "text", value: item.value ?? "" });
    const hint = h("span", { class: "hint" }, "Separate tags with commas");
    return field(item, [input, hint], () => ({ ...item, value: input.value }));
  },
  inputbool: (item) => {
    const box = h("input", { type: "checkbox", checked: !!item.value });
    const node = h("label", { class: "switch field" }, box, item.name);
    return { node, read: () => ({ ...item, value: box.checked }) };
  },
  inputselect: (item) => {
    const select = h(
      "select",
      {},
      Object.entries(item.options || {}).map(([value, label]) =>
        h("option", { value, selected: value === item.value }, label),
      ),
    );
    return field(item, select, () => ({ ...item, value: select.value }));
  },
  inputcheckbox: (item) => {
    const chosen = new Set(item.values || []);
    const boxes = Object.entries(item.options || {}).map(([value, label]) => {
      const box = h("input", {
        type: "checkbox",
        value,
        checked: chosen.has(value),
      });
      return { box, row: h("label", {}, box, label) };
    });
    const list = h(
      "div",
      { class: "check-list" },
      boxes.map((entry) => entry.row),
    );
    const read = () => ({
      ...item,
      values: boxes
        .filter((entry) => entry.box.checked)
        .map((entry) => entry.box.value),
    });
    return field(item, list, read);
  },
  displayinfo: (item) => {
    const node = h("div", { class: "field" }, h("span", {}, item.name));
    const text = h("div", { class: "hint" });
    text.innerHTML = item.value || ""; // trusted help text from the server
    node.append(text);
    return { node, read: () => item };
  },
  displayimage: (item) => ({
    node: h(
      "div",
      { class: "field" },
      h("span", {}, item.name),
      h("img", { src: item.value, alt: item.name }),
    ),
    read: () => item,
  }),
};

function field(item, control, read) {
  const node = h("div", { class: "field" }, h("span", {}, item.name), control);
  return { node, read };
}

/** Build the form; `values()` returns the items to post back. */
export function buildConfigForm(items) {
  const parts = items.map((item) => {
    const render = RENDERERS[item.type];
    return render ? render(item) : { node: null, read: () => item };
  });
  const form = h(
    "form",
    { onsubmit: (event) => event.preventDefault() },
    parts.map((part) => part.node),
  );
  return { form, values: () => parts.map((part) => part.read()) };
}
