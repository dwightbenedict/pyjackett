// "Cache" tab: releases recently returned to Torznab clients.
import { api } from "./api.js";
import { clear, h } from "./dom.js";
import { mountResultsTable } from "./results-table.js";

export async function renderCache(view) {
  const releases = await api.cache();
  const output = h("div", {});
  clear(view).append(
    h(
      "div",
      { class: "view-head" },
      h("h1", {}, "Cached results"),
      h("span", { class: "muted" }, `${releases.length} releases in memory`),
    ),
    output,
  );
  mountResultsTable(output, releases);
}
