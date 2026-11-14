// "Search" tab: the form; submitting opens the results view.
import { api } from "./api.js";
import { standardCategories } from "./categories.js";
import { clear, h } from "./dom.js";
import { symbol } from "./icons.js";
import { multiFilter } from "./multi-filter.js";
import {
  clearRecentSearches,
  recentSearches,
  rememberSearch,
} from "./search-history.js";
import { searchField } from "./search-field.js";
import { renderSearchResults } from "./search-results.js";
import { CONFIGURED_KEY, loadStale } from "./stale-cache.js";

const RESULTS_ROUTE = "#search/results";

function preselectedTracker() {
  const query = location.hash.split("?")[1] || "";
  return new URLSearchParams(query).get("tracker");
}

const split = (csv) => (csv ? csv.split(",") : []);

// ---- form ----

function initialTrackers(request) {
  const preselected = preselectedTracker();
  return preselected ? [preselected] : split(request?.trackers);
}

function trackerFilter(indexers, selected, onChange) {
  return multiFilter({
    all: "All Indexers",
    noun: "Indexers",
    options: indexers.map((i) => [i.id, i.name]),
    selected,
    onChange,
  });
}

// Categories on offer are those of the picked indexers (all if none).
function categoryOptions(indexers, trackerIds) {
  const picked = indexers.filter((i) => trackerIds.includes(i.id));
  return standardCategories(picked.length ? picked : indexers).map(
    ([id, name]) => [String(id), name],
  );
}

function categoryFilter(options, request) {
  const offered = new Set(options.map(([id]) => id));
  return multiFilter({
    all: "All Categories",
    noun: "Categories",
    options,
    selected: split(request?.categories).filter((id) => offered.has(id)),
  });
}

// Same bar as the Indexers tab: the inputs first, the action below them.
function searchBar({ query, trackers, categories, submit }) {
  return h(
    "form",
    { class: "filter-bar" },
    searchField(query),
    h("div", { class: "filter-selects" }, trackers.root, categories.root),
    submit,
  );
}

// ---- recent searches ----

// "Name" for one pick, "N Noun" for several; ids without a name are skipped.
function pickedSummary(csv, names, noun) {
  const picked = split(csv).filter((id) => names.has(id));
  if (picked.length > 1) return `${picked.length} ${noun}`;
  return picked.length ? names.get(picked[0]) : "";
}

function recentDetail(request, { indexers, categories }) {
  const names = (pairs) => new Map(pairs);
  return [
    pickedSummary(
      request.trackers,
      names(indexers.map((i) => [i.id, i.name])),
      "Indexers",
    ),
    pickedSummary(
      request.categories,
      names(categories.map(([id, name]) => [String(id), name])),
      "Categories",
    ),
  ]
    .filter(Boolean)
    .join(" · ");
}

function recentRow(request, open, lookup) {
  const detail = recentDetail(request, lookup);
  return h(
    "button",
    { class: "recent-row", type: "button", onclick: () => open(request) },
    symbol("magnifyingglass", 18),
    h(
      "span",
      { class: "recent-query" },
      request.query,
      detail ? h("small", { class: "recent-detail" }, detail) : null,
    ),
  );
}

function recentList(open, redraw, lookup) {
  const recent = recentSearches();
  if (!recent.length) {
    return h("div", { class: "empty" }, symbol("magnifyingglass", 40, 1.4));
  }
  const clearAll = () => {
    clearRecentSearches();
    redraw();
  };
  return h(
    "section",
    {},
    h(
      "div",
      { class: "section-head" },
      h("h2", {}, "Recent Searches"),
      h(
        "button",
        { class: "bar-btn", type: "button", onclick: clearAll },
        "Clear",
      ),
    ),
    h(
      "div",
      { class: "card recent-list" },
      recent.map((r) => recentRow(r, open, lookup)),
    ),
  );
}

async function renderForm(view, state) {
  const indexers = await loadStale(CONFIGURED_KEY, () => api.indexers(true));
  const chosen = initialTrackers(state.search);
  const categories = categoryFilter(
    categoryOptions(indexers, chosen),
    state.search,
  );
  const trackers = trackerFilter(indexers, chosen, () =>
    categories.setOptions(categoryOptions(indexers, trackers.list())),
  );
  const controls = {
    query: h("input", {
      type: "search",
      placeholder: "Title or IMDb ID, e.g. tt0133093",
      autofocus: true,
      value: state.search?.query ?? "",
    }),
    trackers,
    categories,
    submit: h("button", { class: "btn primary", type: "submit" }, "Search"),
  };
  const bar = searchBar(controls);
  const open = (request) => {
    state.search = request;
    rememberSearch(request);
    // Already on the results route (e.g. after a reload): no hashchange
    // would fire, so ask the router to redraw.
    if (location.hash === RESULTS_ROUTE) {
      window.dispatchEvent(new Event("hashchange"));
    }
    location.hash = RESULTS_ROUTE;
  };
  bar.addEventListener("submit", (event) => {
    event.preventDefault();
    open({
      query: controls.query.value,
      trackers: controls.trackers.values(),
      categories: controls.categories.values(),
    });
  });
  const recent = h("div", {});
  const lookup = { indexers, categories: standardCategories(indexers) };
  const showRecent = () =>
    clear(recent).append(recentList(open, showRecent, lookup));
  showRecent();
  clear(view).append(
    h("div", { class: "view-head" }, h("h1", {}, "Search")),
    bar,
    recent,
  );
}

export function renderSearch(view, state) {
  const onResults = location.hash.startsWith(RESULTS_ROUTE);
  return onResults && state.search
    ? renderSearchResults(view, state)
    : renderForm(view, state);
}
