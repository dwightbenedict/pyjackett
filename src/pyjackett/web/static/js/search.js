// "Search" tab: manual search across configured indexers.
import { api } from "./api.js";
import { clear, h } from "./dom.js";
import { toast, withBusy } from "./feedback.js";
import { mountResultsTable } from "./results-table.js";

const CUSTOM_CATEGORY_START = 100000;

function standardCategories(indexers) {
  const categories = new Map();
  for (const indexer of indexers) {
    for (const cap of indexer.caps) {
      if (Number(cap.ID) < CUSTOM_CATEGORY_START) {
        categories.set(cap.ID, cap.Name);
      }
    }
  }
  return [...categories].sort((a, b) => Number(a[0]) - Number(b[0]));
}

function preselectedTracker() {
  const query = location.hash.split("?")[1] || "";
  return new URLSearchParams(query).get("tracker");
}

function selectedValues(select) {
  return [...select.selectedOptions].map((o) => o.value).join(",");
}

function statusBadge(status) {
  const ok = status.status === "ok";
  return h(
    "span",
    {
      class: `badge ${ok ? "ok" : "danger"}`,
      title:
        status.error || `${status.results} results in ${status.elapsed_ms} ms`,
    },
    `${status.name}: ${ok ? status.results : "error"}`,
  );
}

function indexerStatuses(statuses) {
  return h(
    "div",
    { class: "badges", style: "margin-bottom:12px" },
    statuses.map(statusBadge),
  );
}

// ---- form controls ----

function trackerSelect(indexers) {
  const preselected = preselectedTracker();
  return h(
    "select",
    { multiple: true, size: 6 },
    indexers.map((i) =>
      h("option", { value: i.id, selected: i.id === preselected }, i.name),
    ),
  );
}

function categorySelect(indexers) {
  return h(
    "select",
    { multiple: true, size: 6 },
    standardCategories(indexers).map(([id, name]) =>
      h("option", { value: id }, name),
    ),
  );
}

function labelled(text, control) {
  return h("label", { class: "field" }, h("span", {}, text), control);
}

function searchForm({ query, trackers, categories, submit, onsubmit }) {
  return h(
    "form",
    { class: "card card-pad", style: "margin-bottom:20px", onsubmit },
    labelled("Query", query),
    h(
      "div",
      { class: "two-col" },
      labelled("Indexers (none selected = all)", trackers),
      labelled("Categories (none selected = all)", categories),
    ),
    submit,
  );
}

// ---- running a search ----

async function runSearch(controls, state, output) {
  clear(output).append(h("p", { class: "muted" }, "Searching…"));
  try {
    const reply = await api.search(state.apiKey, {
      query: controls.query.value,
      "Tracker[]": selectedValues(controls.trackers),
      "Category[]": selectedValues(controls.categories),
    });
    clear(output).append(indexerStatuses(reply.indexers));
    mountResultsTable(output, reply.results);
  } catch (error) {
    clear(output);
    toast(error.message, "error");
  }
}

export async function renderSearch(view, state) {
  const indexers = await api.indexers(true);
  const controls = {
    query: h("input", {
      type: "search",
      placeholder: "Search for a title, or an IMDb id like tt0133093",
      autofocus: true,
    }),
    trackers: trackerSelect(indexers),
    categories: categorySelect(indexers),
    submit: h("button", { class: "btn primary", type: "submit" }, "Search"),
  };
  const output = h("div", {});
  controls.onsubmit = (event) => {
    event.preventDefault();
    withBusy(controls.submit, () => runSearch(controls, state, output));
  };
  clear(view).append(
    h("div", { class: "view-head" }, h("h1", {}, "Manual search")),
    searchForm(controls),
    output,
  );
}
