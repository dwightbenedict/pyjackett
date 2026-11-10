// Entry point: tabs, routing, theme and the shared state.
import { api } from "./api.js";
import { renderCache } from "./cache.js";
import { copyText, toast } from "./feedback.js";
import { h } from "./dom.js";
import { renderIndexers } from "./indexers.js";
import { renderLogs } from "./logs.js";
import { renderSearch } from "./search.js";
import { renderSettings } from "./settings.js";

const state = { apiKey: "" };
const VIEWS = {
  indexers: { label: "Indexers", render: renderIndexers },
  search: { label: "Search", render: renderSearch },
  cache: { label: "Cache", render: renderCache },
  logs: { label: "Logs", render: renderLogs },
  settings: { label: "Settings", render: renderSettings },
};
const THEME_KEY = "pyjackett-theme";

// ---- theme ----

function storedTheme() {
  try {
    return localStorage.getItem(THEME_KEY);
  } catch {
    return null;
  }
}

function currentTheme() {
  return (
    document.documentElement.dataset.theme ||
    (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
  );
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const button = document.getElementById("theme");
  button.textContent = theme === "dark" ? "☀" : "☾";
  button.title =
    theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
}

function setupTheme() {
  const saved = storedTheme();
  if (saved) document.documentElement.dataset.theme = saved;
  applyTheme(currentTheme());
  document.getElementById("theme").addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    applyTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* storage may be unavailable */
    }
  });
}

// ---- routing ----

function routeName() {
  const name = location.hash.replace(/^#/, "").split("?")[0];
  return VIEWS[name] ? name : "indexers";
}

function drawTabs(active) {
  const tabs = document.getElementById("tabs");
  tabs.replaceChildren(
    ...Object.entries(VIEWS).map(([name, view]) =>
      h(
        "a",
        {
          class: "tab",
          href: `#${name}`,
          "aria-current": name === active ? "page" : null,
        },
        view.label,
      ),
    ),
  );
}

async function show() {
  const name = routeName();
  drawTabs(name);
  const view = document.getElementById("view");
  try {
    await VIEWS[name].render(view, state);
  } catch (error) {
    view.replaceChildren(
      h(
        "div",
        { class: "card empty" },
        h("h2", {}, "Something went wrong"),
        h("p", {}, error.message),
      ),
    );
    toast(error.message, "error");
  }
}

// ---- start ----

async function start() {
  setupTheme();
  const config = await api.serverConfig();
  state.apiKey = config.api_key;
  document.getElementById("api-key-value").textContent = config.api_key;
  document
    .getElementById("api-key")
    .addEventListener("click", () => copyText(state.apiKey, "API key copied"));
  document.getElementById("logout").hidden = !config.password;
  document.getElementById("logout").textContent = "⎋";
  window.addEventListener("hashchange", show);
  await show();
}

start().catch((error) => toast(error.message, "error"));
