// "Logs" tab: the most recent log lines, refreshed automatically.
import { api } from "./api.js";
import { clear, h } from "./dom.js";
import { iconButton, spinner, symbol } from "./icons.js";
import { confirmDialog } from "./modal.js";
import { statusFilter } from "./status-filter.js";
import { hideOnScrollDown } from "./sticky-bar.js";

const REFRESH_MILLISECONDS = 5000;
const LEVELS = ["Debug", "Info", "Warning", "Error", "Critical"];

function line(entry) {
  const time = new Date(entry.When).toLocaleTimeString();
  return h(
    "div",
    { class: `log-line lvl-${entry.Level}` },
    h("span", { class: "log-time" }, time),
    h("span", { class: "lvl" }, entry.Level),
    h("span", { class: "log-source" }, entry.Source),
    h("span", { class: "log-message" }, entry.Message),
  );
}

/** Same layout as the search results' empty state. */
function empty() {
  return h(
    "div",
    { class: "empty" },
    symbol("doc.text", 40, 1.4),
    h("h2", {}, "No Logs"),
  );
}

/** Swap the icon for the spinner while `work` runs. */
async function spinWhile(button, work) {
  const icon = [...button.childNodes];
  button.replaceChildren(spinner(20));
  try {
    await work();
  } finally {
    button.replaceChildren(...icon);
  }
}

/** Refresh button; its icon spins while the logs load. */
function refreshButton(draw) {
  let busy = false;
  return iconButton("arrow.clockwise", "Refresh", async (event) => {
    if (busy) return;
    busy = true;
    try {
      await spinWhile(event.currentTarget, draw);
    } finally {
      busy = false;
    }
  });
}

/** Clear button; asks "are you sure" before wiping. */
function clearButton(wipe) {
  return iconButton("trash", "Clear Logs", async () => {
    const sure = await confirmDialog({
      title: "Clear Logs?",
      message: "Removes all entries.",
      confirmLabel: "Clear",
      destructive: true,
    });
    if (sure) await wipe();
  });
}

/** Level menu styled like the sort menu of the search results. */
function levelFilter(filters, redraw) {
  const options = LEVELS.map((level) => [level, level]);
  return h(
    "div",
    { class: "results-filter" },
    statusFilter("Level", options, filters, "level", redraw, false),
  );
}

/** Debug when debug logging is on, otherwise Info. */
async function defaultLevel() {
  const config = await api.serverConfig();
  return config.logging ? "Debug" : "Info";
}

export async function renderLogs(view) {
  const list = h("div", { class: "card log-list" });
  const [level, first] = await Promise.all([defaultLevel(), api.logs()]);
  const filters = { level };
  const filter = levelFilter(filters, () => draw());
  const draw = async (fetched = null) => {
    const all = fetched ?? (await api.logs());
    const floor = LEVELS.indexOf(filters.level);
    const entries = all.filter((e) => LEVELS.indexOf(e.Level) >= floor);
    list.className = entries.length ? "card log-list" : "";
    clear(list).append(...(entries.length ? entries.map(line) : [empty()]));
  };
  const wipe = async () => {
    await api.clearLogs();
    await draw();
  };
  const head = h(
    "div",
    { class: "view-head sticky-head" },
    h("h1", {}, "Logs"),
    h(
      "div",
      { class: "toolbar" },
      filter,
      refreshButton(draw),
      clearButton(wipe),
    ),
  );
  clear(view).append(head, list);
  hideOnScrollDown(head);
  await draw(first);
  const timer = setInterval(() => {
    if (view.hidden || !view.contains(list)) clearInterval(timer);
    else draw();
  }, REFRESH_MILLISECONDS);
}
