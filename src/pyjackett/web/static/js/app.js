// Entry point: tabs, routing and the shared state.
import { renderAccount } from "./account.js";
import { api } from "./api.js";
import { h } from "./dom.js";
import { spinner } from "./icons.js";
import { renderIndexers } from "./indexers.js";
import { renderLogs } from "./logs.js";
import { renderSearch } from "./search.js";
import { ALL_KEY, CONFIGURED_KEY, loadStale } from "./stale-cache.js";
import { tabIcon } from "./tab-icons.js";
import { setupTheme } from "./theme.js";

const state = { apiKey: "" };
const VIEWS = {
  indexers: { label: "Indexers", render: renderIndexers, keep: true },
  search: { label: "Search", render: renderSearch, keep: true },
  logs: { label: "Logs", render: renderLogs },
  account: { label: "Account", render: renderAccount, tab: false },
};

// ---- routing ----

function routeName() {
  const name = location.hash.replace(/^#/, "").split(/[/?]/)[0];
  return VIEWS[name] ? name : "indexers";
}

// A tab reopens where it was left (e.g. the search results), as on iOS.
// Only sub-pages count; a query such as `?tracker=` is a one-off.
const lastHash = new Map();

function rememberRoute(name) {
  const sub = location.hash.replace(/^#/, "").split("?")[0];
  if (sub.includes("/")) lastHash.set(name, `#${sub}`);
  else lastHash.delete(name);
}

function drawTabs(active) {
  const tabs = document.getElementById("tabs");
  tabs.replaceChildren(
    ...Object.entries(VIEWS)
      .filter(([, view]) => view.tab !== false)
      .map(([name, view]) =>
        h(
          "a",
          {
            class: "tab",
            href: lastHash.get(name) ?? `#${name}`,
            "aria-current": name === active ? "page" : null,
          },
          tabIcon(name),
          view.label,
        ),
      ),
  );
  const account = document.getElementById("account");
  if (active === "account") account.setAttribute("aria-current", "page");
  else account.removeAttribute("aria-current");
}

// ---- panes ----

// Each tab draws into its own pane, so leaving a tab hides its page instead
// of tearing it down. Views marked `keep` are not rebuilt on return.
const panes = new Map();
const scrolls = new Map();
let shown = null;

function paneFor(name) {
  if (!panes.has(name)) {
    const pane = h(
      "div",
      { class: "pane", hidden: true, dataset: { tab: name } },
      h("div", { class: "pane-loading" }, spinner(28)),
    );
    document.getElementById("view").append(pane);
    panes.set(name, pane);
  }
  return panes.get(name);
}

// Hide every other pane and remember where the one being left was scrolled.
function switchTo(name) {
  if (shown && shown !== name) scrolls.set(shown, window.scrollY);
  const pane = paneFor(name);
  panes.forEach((other) => {
    other.hidden = other !== pane;
  });
  shown = name;
  return pane;
}

async function show() {
  const name = routeName();
  rememberRoute(name);
  drawTabs(name);
  const view = switchTo(name);
  const { keep, render } = VIEWS[name];
  if (keep) window.scrollTo(0, scrolls.get(name) ?? 0);
  try {
    await render(view, state);
  } catch (error) {
    view.replaceChildren(
      h(
        "div",
        { class: "card empty" },
        h("h2", {}, "Something Went Wrong"),
        h("p", {}, error.message),
      ),
    );
  }
}

// ---- start ----

// Fetch the lists the other tabs open with, so a first switch is instant.
function warmCaches() {
  const warm = (key, fetcher) => loadStale(key, fetcher).catch(() => {});
  // The Indexers tab loads its own list when it is the first one shown.
  if (routeName() !== "indexers") warm(ALL_KEY, () => api.indexers());
  if (routeName() !== "search") {
    warm(CONFIGURED_KEY, () => api.indexers(true));
  }
}

async function start() {
  setupTheme();
  const config = await api.serverConfig();
  state.apiKey = config.api_key;
  window.addEventListener("hashchange", show);
  warmCaches();
  await show();
}

start();
