// Form field builders shared by the settings pages: {node, read}.
import { api } from "./api.js";
import { h } from "./dom.js";

export const PROXY_TYPES = {
  0: "HTTP",
  1: "SOCKS4",
  2: "SOCKS5",
};

export function text(
  label,
  name,
  config,
  { type = "text", hint, placeholder } = {},
) {
  const input = h("input", {
    type,
    name,
    value: config[name] ?? "",
    placeholder,
  });
  const note = hint ? h("span", { class: "hint" }, hint) : null;
  return {
    node: h("label", { class: "field" }, h("span", {}, label), input, note),
    read: () => (type === "number" ? Number(input.value) : input.value),
  };
}

export function toggle(label, name, config) {
  const box = h("input", { type: "checkbox", checked: !!config[name] });
  return {
    node: h("label", { class: "switch field" }, box, label),
    read: () => box.checked,
  };
}

export function proxyType(config) {
  const options = Object.entries(PROXY_TYPES).map(([value, name]) =>
    h(
      "option",
      { value, selected: String(config.proxy_type) === value },
      name,
    ),
  );
  const select = h("select", {}, options);
  return {
    node: h("label", { class: "field" }, h("span", {}, "Proxy Type"), select),
    read: () => Number(select.value),
  };
}

/** Read every field of the given groups into one {key: value} object. */
export function readFields(groups) {
  const values = {};
  for (const fields of groups) {
    for (const [key, field] of Object.entries(fields)) {
      values[key] = field.read();
    }
  }
  return values;
}

/** The server expects the whole form, so merge edits over the saved config. */
export async function saveConfigFields(groups) {
  const config = await api.serverConfig();
  return api.saveServerConfig({ ...config, ...readFields(groups) });
}
