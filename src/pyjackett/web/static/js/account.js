// "Account" page: sign-in, API access, server settings and appearance.
import { api, paths } from "./api.js";
import { clear, h } from "./dom.js";
import {
  PROXY_TYPES,
  proxyType,
  saveConfigFields,
  text,
  toggle,
} from "./fields.js";
import { copyLabel, copyWithConfirmation, withBusy } from "./feedback.js";
import { alertDialog, confirmDialog, passwordDialog } from "./modal.js";
import { THEMES, setTheme, storedTheme } from "./theme.js";

const THEME_LABELS = { system: "System", light: "Light", dark: "Dark" };

function card(...children) {
  return h("section", { class: "card card-pad" }, ...children);
}

function button(label, onclick, kind = "") {
  return h(
    "button",
    { class: `btn ${kind}`.trim(), type: "button", onclick },
    label,
  );
}

// ---- sign-in ----

const WARNING =
  '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.3 3.9L2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>';

async function saveSignIn(save, username, password, redraw) {
  await withBusy(save, async () => {
    await api.setAdminUsername(username.value);
    if (password.value) await api.setAdminPassword(password.value);
    redraw();
  });
}

function signInCard(config, redraw) {
  const username = h("input", {
    type: "text",
    value: config.username,
    autocomplete: "username",
    required: true,
  });
  const password = h("input", {
    type: "password",
    autocomplete: "new-password",
  });
  const save = button(
    "Save",
    () => saveSignIn(save, username, password, redraw),
    "primary",
  );
  const warning = config.default_credentials
    ? h(
        "p",
        { class: "form-warning" },
        icon(WARNING),
        "Default Credentials in Use",
      )
    : null;
  return card(
    warning,
    h("label", { class: "field" }, h("span", {}, "Username"), username),
    h("label", { class: "field" }, h("span", {}, "New Password"), password),
    h("div", { class: "actions" }, save),
  );
}

// ---- API access ----

const EXTERNAL_LINK =
  '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17L17 7M8 7h9v9"/></svg>';

async function regenerateKey(regenerate, config, state, redraw) {
  const sure = await confirmDialog({
    title: "Regenerate API Key?",
    message: "Old URLs will stop working.",
    confirmLabel: "Regenerate",
    destructive: true,
  });
  if (!sure) return;
  // `config.password` is a non-empty hash prefix only when a password is set.
  const password = config.password
    ? await passwordDialog({ title: "Admin Password" })
    : null;
  if (config.password && password === null) return;
  await withBusy(regenerate, async () => {
    try {
      const reply = await api.rotateApiKey(password);
      state.apiKey = reply.api_key;
      redraw();
    } catch (error) {
      await alertDialog({
        title: "Could Not Regenerate",
        message: error.message,
      });
    }
  });
}

function apiCard(config, state, redraw) {
  const copyButton = button(copyLabel(), (event) =>
    copyWithConfirmation(event.currentTarget, config.api_key),
  );
  const regenerate = button("Regenerate", () =>
    regenerateKey(regenerate, config, state, redraw),
  );
  return card(
    h("input", {
      type: "text",
      class: "api-key",
      value: config.api_key,
      readonly: true,
      "aria-label": "API key",
    }),
    h(
      "div",
      { class: "actions" },
      copyButton,
      regenerate,
      h(
        "a",
        {
          class: "btn",
          href: `${paths.base}/api/v1/docs`,
          target: "_blank",
          rel: "noopener",
        },
        "API Docs",
        icon(EXTERNAL_LINK),
      ),
    ),
  );
}

// ---- config-backed cards (network, proxy) ----

async function saveFields(save, fields, state) {
  await withBusy(save, async () => {
    try {
      const reply = await saveConfigFields([fields]);
      state.apiKey = reply.api_key;
    } catch (error) {
      await alertDialog({ title: "Could Not Save", message: error.message });
    }
  });
}

/** Nodes in field order; the `inline` names share one row with `save`. */
function fieldNodes(fields, inline, save) {
  const nodes = [];
  const row = h("div", { class: "field-row" });
  for (const [name, field] of Object.entries(fields)) {
    if (!inline.includes(name)) {
      nodes.push(field.node);
      continue;
    }
    if (!nodes.includes(row)) nodes.push(row);
    row.append(field.node);
  }
  if (nodes.at(-1) === row) row.append(save);
  return nodes;
}

function fieldsCard(fields, state, inline = []) {
  const save = button(
    "Save",
    () => saveFields(save, fields, state),
    "primary",
  );
  const nodes = fieldNodes(fields, inline, save);
  if (!save.parentNode) nodes.push(h("div", { class: "actions" }, save));
  return card(nodes);
}

/** A card without a Save button: every change is saved as it is made. */
function autosaveCard(fields, state) {
  const node = card(Object.values(fields).map((field) => field.node));
  node.addEventListener("change", () => saveFields(node, fields, state));
  return node;
}

function networkCards(config, state) {
  const address = {
    local_bind_address: text("Local Address", "local_bind_address", config),
    port: text("Port", "port", config, { type: "number" }),
  };
  const access = {
    external: toggle("Allow External Access", "external", config),
    cors: toggle("Allow CORS Requests", "cors", config),
  };
  return [
    fieldsCard(address, state, ["local_bind_address", "port"]),
    fieldsCard(publicUrl(config), state),
    autosaveCard(access, state),
  ];
}

/** Blank means "derive it"; the placeholder shows what is in use now. */
function publicUrl(config) {
  return {
    basepathoverride: text("Base Path", "basepathoverride", config, {
      hint: "For reverse proxies, e.g. /jackett",
      placeholder: paths.base || "/",
    }),
    baseurloverride: text("Base URL", "baseurloverride", config, {
      hint: "e.g. https://example.com",
      placeholder: window.location.origin,
    }),
  };
}

/** Both proxy cards write proxy_type; -1 (disabled) wins while it is off. */
function proxyCards(config, state) {
  const enabled = toggle("Use Proxy", "proxy_enabled", {
    proxy_enabled: config.proxy_type !== -1,
  });
  const type = proxyType(config);
  const effectiveType = () => (enabled.read() ? type.read() : -1);
  const power = { proxy_type: { node: enabled.node, read: effectiveType } };
  const settings = proxyFields(config, { ...type, read: effectiveType });
  const form = fieldsCard(settings, state, ["proxy_url", "proxy_port"]);
  const sync = () => {
    for (const input of form.querySelectorAll("input, select")) {
      input.disabled = !enabled.read();
    }
  };
  enabled.node.addEventListener("change", sync);
  sync();
  return [autosaveCard(power, state), form];
}

function proxyFields(config, type) {
  return {
    proxy_type: type,
    proxy_url: text("Host", "proxy_url", config),
    proxy_port: text("Port", "proxy_port", config, { type: "number" }),
    proxy_username: text("Username (Optional)", "proxy_username", config),
    proxy_password: text("Password (Optional)", "proxy_password", config, {
      type: "password",
    }),
  };
}

// ---- integrations ----

function integrationCards(config, state) {
  const flaresolverr = {
    flaresolverrurl: text("FlareSolverr URL", "flaresolverrurl", config, {
      hint: "e.g. http://127.0.0.1:8191",
    }),
    flaresolverr_maxtimeout: text(
      "FlareSolverr Max Timeout (ms)",
      "flaresolverr_maxtimeout",
      config,
      { type: "number" },
    ),
  };
  const omdb = {
    omdbkey: text("OMDb API Key", "omdbkey", config, {
      hint: "Improves IMDb searches",
    }),
    omdburl: text("OMDb API URL", "omdburl", config),
  };
  return [fieldsCard(flaresolverr, state), fieldsCard(omdb, state)];
}

// ---- cache, downloads, diagnostics ----

function cacheCards(config, state) {
  const power = {
    cache_enabled: toggle("Enable Cache", "cache_enabled", config),
  };
  const limits = {
    cache_ttl: text("Cache TTL (Seconds)", "cache_ttl", config, {
      type: "number",
    }),
    cache_max_results_per_indexer: text(
      "Max Cached Results per Indexer",
      "cache_max_results_per_indexer",
      config,
      { type: "number" },
    ),
  };
  const form = fieldsCard(limits, state);
  const sync = () => {
    for (const input of form.querySelectorAll("input, select")) {
      input.disabled = !power.cache_enabled.read();
    }
  };
  power.cache_enabled.node.addEventListener("change", sync);
  sync();
  return [autosaveCard(power, state), form];
}

function testingCards(config, state) {
  const limits = {
    test_timeout: text("Timeout (Seconds)", "test_timeout", config, {
      type: "number",
      hint: "How long an indexer test may take",
    }),
  };
  return [fieldsCard(limits, state)];
}

function downloadCards(config, state) {
  const blackhole = {
    blackholedir: text("Blackhole Directory", "blackholedir", config, {
      hint: "Where .torrent files are saved",
    }),
  };
  return [fieldsCard(blackhole, state)];
}

function diagnosticCards(config, state) {
  const logging = {
    logging: toggle("Debug Logging", "logging", config),
  };
  const updates = {
    updatedisabled: toggle("Disable Update Checks", "updatedisabled", config),
    prerelease: toggle("Include Pre-Releases", "prerelease", config),
  };
  return [autosaveCard(logging, state), autosaveCard(updates, state)];
}

// ---- appearance ----

function appearanceCard() {
  const current = storedTheme();
  const options = THEMES.map((theme) => {
    const radio = h("input", {
      class: "row-check",
      type: "radio",
      name: "theme",
      value: theme,
      checked: theme === current,
      onchange: () => setTheme(theme),
    });
    return h(
      "label",
      { class: "row" },
      h("span", {}, THEME_LABELS[theme]),
      radio,
    );
  });
  return h(
    "div",
    { class: "list", role: "radiogroup", "aria-label": "Theme" },
    options,
  );
}

// ---- page ----

const CHEVRON_LEFT =
  '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>';
const CHEVRON_RIGHT =
  '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>';

function icon(markup) {
  const span = h("span", { class: "chevron" });
  span.innerHTML = markup;
  return span;
}

/** Each row of the list opens a page of its own: #account/<id>. */
function sections(config, state) {
  return {
    ...accessSections(config, state),
    ...serverSections(config, state),
    appearance: {
      label: "Appearance",
      value: THEME_LABELS[storedTheme()],
      body: appearanceCard,
    },
  };
}

function accessSections(config, state) {
  return {
    signin: {
      label: "Sign In",
      value: config.username,
      body: (redraw) => signInCard(config, redraw),
    },
    api: {
      label: "API",
      value: "",
      body: (redraw) => apiCard(config, state, redraw),
    },
  };
}

function serverSections(config, state) {
  const proxy = PROXY_TYPES[config.proxy_type];
  return {
    network: {
      label: "Network",
      value: `${config.local_bind_address}:${config.port}`,
      body: () => networkCards(config, state),
    },
    proxy: {
      label: "Proxy",
      value: config.proxy_type === -1 ? "Off" : proxy,
      body: () => proxyCards(config, state),
    },
    integrations: {
      label: "Integrations",
      value: config.omdbkey ? "OMDb on" : "",
      body: () => integrationCards(config, state),
    },
    cache: {
      label: "Cache",
      value: config.cache_enabled ? "On" : "Off",
      body: () => cacheCards(config, state),
    },
    testing: {
      label: "Testing",
      value: `${config.test_timeout} s`,
      body: () => testingCards(config, state),
    },
    downloads: {
      label: "Downloads",
      value: "",
      body: () => downloadCards(config, state),
    },
    diagnostics: {
      label: "Diagnostics",
      value: config.logging ? "Debug Logging" : "",
      body: () => diagnosticCards(config, state),
    },
  };
}

/** Related rows share a list; each group is drawn as its own card. */
const GROUPS = [
  ["signin", "api"],
  ["network", "proxy", "integrations"],
  ["cache", "testing", "downloads", "diagnostics"],
  ["appearance"],
];

function backButton(href) {
  const link = h("a", { class: "back-btn", href, "aria-label": "Back" });
  link.innerHTML = CHEVRON_LEFT;
  return link;
}

function header(title, backHref) {
  return h(
    "div",
    { class: "sheet-head" },
    backButton(backHref),
    h("h1", {}, title),
    h("span"),
  );
}

function row(id, { label, value }) {
  return h(
    "a",
    { class: "row", href: `#account/${id}` },
    h("span", {}, label),
    h("span", { class: "row-value" }, value),
    icon(CHEVRON_RIGHT),
  );
}

function signOutRow() {
  return h(
    "a",
    { class: "row danger", href: `${paths.base}/UI/Logout` },
    h("span", {}, "Sign Out"),
  );
}

function subRoute() {
  return location.hash.replace(/^#/, "").split("?")[0].split("/")[1];
}

export async function renderAccount(view, state) {
  const config = await api.serverConfig();
  const all = sections(config, state);
  const id = subRoute();
  if (all[id]) {
    const redraw = () => renderAccount(view, state);
    clear(view).append(
      header(all[id].label, "#account"),
      h("div", { class: "sheet" }, all[id].body(redraw)),
    );
    return;
  }
  clear(view).append(
    header("Account", "#indexers"),
    h(
      "div",
      { class: "sheet" },
      GROUPS.map((keys) =>
        h(
          "div",
          { class: "list" },
          keys.map((key) => row(key, all[key])),
        ),
      ),
      h("div", { class: "list" }, signOutRow()),
    ),
  );
}
