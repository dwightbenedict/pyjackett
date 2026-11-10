// Sortable, filterable table of releases (used by Search and Cache tabs).
import { clear, h } from "./dom.js";
import { copyText, toast } from "./feedback.js";
import { formatBytes, formatDate, timeAgo } from "./format.js";

const DEFAULT_PAGE_SIZE = 100;

const COLUMNS = [
  {
    key: "publish_date",
    label: "Published",
    sort: (r) => Date.parse(r.publish_date) || 0,
    cell: (r) =>
      h(
        "span",
        { title: formatDate(r.publish_date) },
        timeAgo(r.publish_date),
      ),
  },
  {
    key: "tracker",
    label: "Tracker",
    sort: (r) => r.tracker || "",
    cell: (r) => r.tracker,
  },
  {
    key: "title",
    label: "Title",
    className: "title-cell",
    sort: (r) => (r.title || "").toLowerCase(),
    cell: (r) =>
      r.details
        ? h(
            "a",
            { href: r.details, target: "_blank", rel: "noreferrer" },
            r.title,
          )
        : r.title,
  },
  {
    key: "category_desc",
    label: "Category",
    sort: (r) => r.category_desc || "",
    cell: (r) => r.category_desc,
  },
  {
    key: "size",
    label: "Size",
    numeric: true,
    sort: (r) => r.size ?? -1,
    cell: (r) => formatBytes(r.size),
  },
  {
    key: "seeders",
    label: "S",
    numeric: true,
    sort: (r) => r.seeders ?? -1,
    cell: (r) => h("span", { class: "seeders" }, r.seeders ?? "—"),
  },
  {
    key: "peers",
    label: "L",
    numeric: true,
    sort: (r) => r.peers ?? -1,
    cell: (r) => h("span", { class: "leechers" }, r.peers ?? "—"),
  },
  {
    key: "grabs",
    label: "Grabs",
    numeric: true,
    sort: (r) => r.grabs ?? -1,
    cell: (r) => r.grabs ?? "—",
  },
];

// ---- row actions ----

function iconButton(label, title, onclick) {
  return h(
    "button",
    { class: "btn small", type: "button", title, onclick },
    label,
  );
}

async function sendToBlackhole(url) {
  const reply = await (await fetch(url)).json();
  if (reply.result === "success") {
    toast("Saved to blackhole folder", "ok");
  } else {
    toast(reply.error || "Blackhole failed", "error");
  }
}

function downloadActions(release) {
  if (!release.link) {
    return [];
  }
  return [
    h(
      "a",
      { class: "btn small", href: release.link, title: "Download .torrent" },
      "⬇",
    ),
    iconButton("⧉", "Copy download link", () =>
      copyText(release.link, "Download link copied"),
    ),
  ];
}

function actions(release) {
  const buttons = downloadActions(release);
  if (release.magnet_uri) {
    buttons.push(
      iconButton("🧲", "Copy magnet link", () =>
        copyText(release.magnet_uri, "Magnet link copied"),
      ),
    );
  }
  if (release.blackhole_link) {
    buttons.push(
      iconButton("⇩", "Send to blackhole folder", () =>
        sendToBlackhole(release.blackhole_link),
      ),
    );
  }
  return h("div", { class: "row-actions" }, buttons);
}

// ---- sorting and filtering ----

function matchesFilter(release, text) {
  const { title, tracker, category_desc: category } = release;
  const haystack = `${title} ${tracker} ${category}`;
  return !text || haystack.toLowerCase().includes(text);
}

function compareBy(column, descending) {
  return (a, b) => {
    const left = column.sort(a);
    const right = column.sort(b);
    const order = left < right ? -1 : left > right ? 1 : 0;
    return descending ? -order : order;
  };
}

function visibleRows(releases, state) {
  const column = COLUMNS.find((c) => c.key === state.sortKey);
  return releases
    .filter((release) => matchesFilter(release, state.filter))
    .sort(compareBy(column, state.descending));
}

// ---- rendering ----

function headerCell(column, state, redraw) {
  const active = column.key === state.sortKey;
  const arrow = active ? (state.descending ? " ▼" : " ▲") : "";
  const sorted = state.descending ? "descending" : "ascending";
  const onclick = () => {
    state.descending = active ? !state.descending : true;
    state.sortKey = column.key;
    redraw();
  };
  return h(
    "th",
    {
      class: `sortable${column.numeric ? " num" : ""}`,
      "aria-sort": active ? sorted : "none",
      onclick,
    },
    column.label + arrow,
  );
}

function bodyRow(release) {
  const cells = COLUMNS.map((column) =>
    h(
      "td",
      { class: `${column.className || ""}${column.numeric ? " num" : ""}` },
      column.cell(release),
    ),
  );
  return h("tr", {}, cells, h("td", {}, actions(release)));
}

function table(rows, state, redraw) {
  const heads = COLUMNS.map((c) => headerCell(c, state, redraw));
  return h(
    "table",
    {},
    h("thead", {}, h("tr", {}, heads, h("th", {}, ""))),
    h("tbody", {}, rows.map(bodyRow)),
  );
}

function emptyMessage() {
  return h(
    "div",
    { class: "empty" },
    h("h2", {}, "No results"),
    h("p", {}, "Nothing to show yet."),
  );
}

function showMore(remaining, onclick) {
  return h(
    "div",
    { class: "empty" },
    h(
      "button",
      { class: "btn", type: "button", onclick },
      `Show more (${remaining} left)`,
    ),
  );
}

function drawBody(body, releases, state, redraw) {
  const rows = visibleRows(releases, state);
  clear(body);
  if (!rows.length) {
    body.append(emptyMessage());
    return;
  }
  const shown = rows.slice(0, state.limit);
  body.append(table(shown, state, redraw));
  if (rows.length > shown.length) {
    body.append(
      showMore(rows.length - shown.length, () => {
        state.limit += DEFAULT_PAGE_SIZE;
        redraw();
      }),
    );
  }
}

/** Mount a results table inside `container`. */
export function mountResultsTable(container, releases) {
  const state = {
    sortKey: "publish_date",
    descending: true,
    filter: "",
    limit: DEFAULT_PAGE_SIZE,
  };
  const body = h("div", { class: "card table-wrap" });
  const redraw = () => drawBody(body, releases, state, redraw);
  const filter = h("input", {
    type: "search",
    placeholder: "Filter results…",
    oninput: (event) => {
      state.filter = event.target.value.toLowerCase();
      redraw();
    },
  });
  container.append(
    h("div", { class: "toolbar", style: "margin-bottom:12px" }, filter),
    body,
  );
  redraw();
}
