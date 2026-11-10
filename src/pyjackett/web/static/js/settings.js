// "Settings" tab: server configuration form.
import { api } from "./api.js";
import { clear, h } from "./dom.js";
import { copyText, toast, withBusy } from "./feedback.js";

const PROXY_TYPES = {
  "-1": "Disabled",
  0: "HTTP",
  1: "SOCKS4",
  2: "SOCKS5",
};

// ---- field builders (each returns {node, read}) ----

function text(label, name, config, { type = "text", hint } = {}) {
  const input = h("input", { type, name, value: config[name] ?? "" });
  const note = hint ? h("span", { class: "hint" }, hint) : null;
  return {
    node: h("label", { class: "field" }, h("span", {}, label), input, note),
    read: () => (type === "number" ? Number(input.value) : input.value),
  };
}

function toggle(label, name, config) {
  const box = h("input", { type: "checkbox", checked: !!config[name] });
  return {
    node: h("label", { class: "switch field" }, box, label),
    read: () => box.checked,
  };
}

function proxyType(config) {
  const options = Object.entries(PROXY_TYPES).map(([value, name]) =>
    h(
      "option",
      { value, selected: String(config.proxy_type) === value },
      name,
    ),
  );
  const select = h("select", {}, options);
  return {
    node: h("label", { class: "field" }, h("span", {}, "Proxy type"), select),
    read: () => Number(select.value),
  };
}

// ---- form definition ----

function networkFields(config) {
  return {
    port: text("Port", "port", config, { type: "number" }),
    external: toggle("Allow external access", "external", config),
    local_bind_address: text(
      "Local bind address",
      "local_bind_address",
      config,
    ),
    cors: toggle("Allow CORS requests", "cors", config),
  };
}

function cacheFields(config) {
  return {
    cache_enabled: toggle("Enable cache", "cache_enabled", config),
    cache_ttl: text("Cache TTL (seconds)", "cache_ttl", config, {
      type: "number",
    }),
    cache_max_results_per_indexer: text(
      "Max cached results per indexer",
      "cache_max_results_per_indexer",
      config,
      { type: "number" },
    ),
  };
}

function proxyFields(config) {
  return {
    proxy_type: proxyType(config),
    proxy_url: text("Proxy host", "proxy_url", config),
    proxy_port: text("Proxy port", "proxy_port", config, { type: "number" }),
    proxy_username: text("Proxy username", "proxy_username", config),
    proxy_password: text("Proxy password", "proxy_password", config, {
      type: "password",
    }),
  };
}

function integrationFields(config) {
  return {
    flaresolverrurl: text("FlareSolverr URL", "flaresolverrurl", config, {
      hint: "e.g. http://127.0.0.1:8191",
    }),
    flaresolverr_maxtimeout: text(
      "FlareSolverr max timeout (ms)",
      "flaresolverr_maxtimeout",
      config,
      { type: "number" },
    ),
    omdbkey: text("OMDb API key", "omdbkey", config, {
      hint: "Improves IMDb searches on the aggregate feeds",
    }),
    omdburl: text("OMDb API URL", "omdburl", config),
  };
}

function downloadFields(config) {
  return {
    blackholedir: text("Blackhole directory", "blackholedir", config, {
      hint: "Folder where .torrent files can be saved",
    }),
    basepathoverride: text("Base path override", "basepathoverride", config, {
      hint: "Only when behind a reverse proxy, e.g. /pyjackett",
    }),
    baseurloverride: text("Base URL override", "baseurloverride", config, {
      hint: "e.g. https://example.com",
    }),
  };
}

function diagnosticFields(config) {
  return {
    logging: toggle("Debug logging", "logging", config),
    updatedisabled: toggle("Disable update checks", "updatedisabled", config),
    prerelease: toggle("Include pre-releases", "prerelease", config),
  };
}

function sections(config) {
  return [
    ["Network", networkFields(config)],
    ["Cache", cacheFields(config)],
    ["Proxy", proxyFields(config)],
    ["Cloudflare & metadata", integrationFields(config)],
    ["Downloads & reverse proxy", downloadFields(config)],
    ["Diagnostics", diagnosticFields(config)],
  ];
}

// ---- side cards ----

async function savePassword(button, input) {
  await withBusy(button, async () => {
    try {
      await api.setAdminPassword(input.value);
      toast(input.value ? "Admin password saved" : "Password removed", "ok");
      location.reload();
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

function passwordCard(config) {
  const input = h("input", { type: "password", autocomplete: "new-password" });
  const label = config.password ? "Change password" : "Set password";
  const save = h("button", { class: "btn", type: "button" }, label);
  save.addEventListener("click", () => savePassword(save, input));
  const note = config.password
    ? "The dashboard is protected. Leave empty and save to remove the password."
    : "The dashboard is open to anyone who can reach this port.";
  return h(
    "section",
    { class: "card card-pad" },
    h("h2", {}, "Admin password"),
    h("p", { class: "muted" }, note),
    h("label", { class: "field" }, h("span", {}, "New password"), input),
    save,
  );
}

function apiKeyCard(config) {
  const copy = () => copyText(config.api_key, "API key copied");
  return h(
    "section",
    { class: "card card-pad" },
    h("h2", {}, "API key"),
    h(
      "p",
      { class: "muted" },
      "Used by Sonarr, Radarr and friends to talk to the Torznab feeds.",
    ),
    h("p", {}, h("code", {}, config.api_key)),
    h("button", { class: "btn", type: "button", onclick: copy }, "Copy"),
  );
}

// ---- saving ----

function readPayload(groups) {
  const payload = {};
  for (const [, fields] of groups) {
    for (const [key, field] of Object.entries(fields)) {
      payload[key] = field.read();
    }
  }
  return payload;
}

async function saveSettings(button, groups, state) {
  await withBusy(button, async () => {
    try {
      const reply = await api.saveServerConfig(readPayload(groups));
      state.apiKey = reply.api_key;
      const restart = "Saved. Restart PyJackett to apply network changes.";
      toast(reply.restart_required ? restart : "Settings saved", "ok", 6000);
    } catch (error) {
      toast(error.message, "error", 9000);
    }
  });
}

function settingsCard([title, fields]) {
  return h(
    "section",
    { class: "card card-pad" },
    h("h2", {}, title),
    Object.values(fields).map((field) => field.node),
  );
}

export async function renderSettings(view, state) {
  const config = await api.serverConfig();
  const groups = sections(config);
  const save = h("button", { class: "btn primary", type: "submit" }, "Save");
  const onsubmit = (event) => {
    event.preventDefault();
    saveSettings(save, groups, state);
  };
  clear(view).append(
    h(
      "div",
      { class: "view-head" },
      h("h1", {}, "Settings"),
      h("span", { class: "muted" }, `PyJackett ${config.app_version}`),
    ),
    h(
      "form",
      { onsubmit },
      h("div", { class: "settings-grid" }, groups.map(settingsCard)),
      h("div", { style: "margin:20px 0" }, save),
    ),
    h(
      "div",
      { class: "settings-grid" },
      apiKeyCard(config),
      passwordCard(config),
    ),
  );
}
