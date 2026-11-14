// Sortable list of releases (used by the Search tab), one stacked row each.
import { clear, h, measure } from "./dom.js";
import { symbol } from "./icons.js";
import { ageParts, bytesParts } from "./format.js";
import { openResultDialog } from "./results-detail.js";
import { createSorter } from "./results-sort.js";

const DEFAULT_PAGE_SIZE = 100;

// Sort keys offered in the sort menu.
const COLUMNS = [
  {
    key: "publish_date",
    label: "Published",
    sort: (r) => Date.parse(r.publish_date) || 0,
  },
  {
    key: "tracker",
    label: "Indexer",
    sort: (r) => r.tracker || "",
  },
  {
    key: "title",
    label: "Title",
    sort: (r) => (r.title || "").toLowerCase(),
  },
  {
    key: "category_desc",
    label: "Category",
    sort: (r) => r.category_desc || "",
  },
  {
    key: "size",
    label: "Size",
    sort: (r) => r.size ?? -1,
  },
  {
    key: "seeders",
    label: "Seeders",
    sort: (r) => r.seeders ?? -1,
  },
  {
    key: "peers",
    label: "Leechers",
    sort: (r) => r.peers ?? -1,
  },
  {
    key: "grabs",
    label: "Grabs",
    sort: (r) => r.grabs ?? -1,
  },
];

function visibleRows(releases, state) {
  return [...releases].sort(state.sorter.compare);
}

// ---- rendering ----

// Small label above the title, like the App Store's, with the category.
function eyebrow(release) {
  return h(
    "div",
    { class: "result-eyebrow" },
    h("span", { class: "result-indexer" }, release.tracker),
    release.category_desc
      ? h("span", { class: "tag" }, release.category_desc)
      : null,
  );
}

function stat(name, label, value) {
  return h(
    "span",
    { class: "stat", title: label, "aria-label": label },
    symbol(name, 13, 2.2),
    Array.isArray(value) ? measure(value) : (value ?? "—"),
  );
}

function statsLine(release) {
  return h(
    "div",
    { class: "result-stats" },
    stat("externaldrive", "Size", bytesParts(release.size)),
    stat("clock", "Published", ageParts(release.publish_date)),
    stat("arrow.up", "Seeders", release.seeders),
    stat("arrow.down", "Leechers", release.peers),
    stat("tray", "Grabs", release.grabs),
  );
}

function resultRow(release) {
  const open = () => openResultDialog(release);
  return h(
    "div",
    {
      class: "result",
      role: "button",
      tabindex: "0",
      onclick: open,
      onkeydown: (event) => {
        if (event.target === event.currentTarget && event.key === "Enter") {
          open();
        }
      },
    },
    eyebrow(release),
    h("div", { class: "result-title" }, release.title),
    statsLine(release),
  );
}

function resultList(rows) {
  return h("div", { class: "result-list" }, rows.map(resultRow));
}

function emptyMessage() {
  return h(
    "div",
    { class: "empty" },
    symbol("magnifyingglass", 40, 1.4),
    h("h2", {}, "No Results"),
  );
}

function showMore(remaining, onclick) {
  return h(
    "div",
    { class: "empty" },
    h(
      "button",
      { class: "btn", type: "button", onclick },
      `Show ${remaining} More`,
    ),
  );
}

function drawBody(body, releases, state, redraw) {
  const rows = visibleRows(releases, state);
  clear(body);
  if (!rows.length) {
    if (state.finished) body.append(emptyMessage());
    return;
  }
  const shown = rows.slice(0, state.limit);
  body.append(resultList(shown));
  if (rows.length > shown.length) {
    body.append(
      showMore(rows.length - shown.length, () => {
        state.limit += DEFAULT_PAGE_SIZE;
        redraw();
      }),
    );
  }
}

/**
 * Mount a results list inside `container`, with its sort menu in
 * `filterHost`. Returns `{ add(more), finish(), refresh() }`; the empty
 * state shows only once the search has finished.
 */
export function mountResultsList(container, releases, filterHost) {
  const body = h("div", {});
  const state = { finished: false, limit: DEFAULT_PAGE_SIZE };
  const redraw = () => drawBody(body, releases, state, redraw);
  state.sorter = createSorter(COLUMNS, redraw);
  filterHost.append(state.sorter.menu);
  container.append(body);
  redraw();
  // Streamed batches are drawn at most once per frame, and only while the
  // list is on screen; a hidden or detached list catches up on `refresh`.
  let dirty = false;
  let frame = 0;
  const onScreen = () =>
    container.isConnected && !container.closest("[hidden]");
  const refresh = () => {
    if (!dirty || !onScreen()) return;
    dirty = false;
    redraw();
  };
  const schedule = () => {
    dirty = true;
    frame ||= requestAnimationFrame(() => {
      frame = 0;
      refresh();
    });
  };
  return {
    refresh,
    finish() {
      state.finished = true;
      schedule();
    },
    add(more) {
      releases.push(...more);
      schedule();
    },
  };
}
