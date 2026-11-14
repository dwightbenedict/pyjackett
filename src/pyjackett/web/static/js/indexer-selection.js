// Multi-select on the Indexers tab: pick cards, then add, test or disable.
import { api } from "./api.js";
import { h } from "./dom.js";
import { withBusy } from "./feedback.js";
import { symbol } from "./icons.js";
import { confirmDialog } from "./modal.js";

const ADDED = { configured: true, healthy: false, failing: false };
const REMOVED = { configured: false, healthy: false, failing: false };

/** The chosen indexer ids. A key keeps redraws from stacking listeners. */
export class Selection {
  constructor() {
    this.ids = new Set();
    this.listeners = new Map();
  }

  has(id) {
    return this.ids.has(id);
  }

  toggle(id) {
    if (!this.ids.delete(id)) this.ids.add(id);
    this.notify();
  }

  replace(ids) {
    this.ids = new Set(ids);
    this.notify();
  }

  listen(key, listener) {
    this.listeners.set(key, listener);
  }

  notify() {
    this.listeners.forEach((listener) => listener());
  }
}

/** The checkmark circle shown on every card while selecting. */
export function selectMark(selected) {
  return h(
    "span",
    { class: `select-mark${selected ? " on" : ""}`, "aria-hidden": "true" },
    symbol("checkmark", 14, 2.6),
  );
}

// ---- actions ----

// One request per indexer, so each card settles when its own test ends.
function testEach(ids, settle) {
  const test = (id) =>
    api.testIndexer(id).then(
      (reply) => ({
        id,
        status: "ok",
        error: null,
        latency_ms: reply?.latency_ms ?? null,
      }),
      (error) => ({
        id,
        status: "error",
        error: error.message,
        latency_ms: error.latencyMs ?? null,
      }),
    );
  return Promise.all(ids.map((id) => test(id).then((o) => (settle(o), o))));
}

const ACTIONS = [
  {
    key: "add",
    label: "Add",
    applies: (indexer) => !indexer.configured,
    call: (ids) => api.bulkAdd(ids),
    onOk: (sync, indexer) => sync.patch(indexer, ADDED),
    onFail: (sync, indexer, { error }) =>
      sync.patch(indexer, { last_error: error }),
  },
  {
    key: "test",
    label: "Test",
    applies: (indexer) => indexer.configured,
    call: testEach,
    streams: true,
    keepSelection: true,
    onOk: (sync, indexer, { latency_ms }) =>
      sync.patchStatus(indexer, {
        healthy: true,
        failing: false,
        latency_ms: latency_ms ?? indexer.latency_ms,
      }),
    onFail: (sync, indexer, { error, latency_ms }) =>
      sync.patchStatus(indexer, {
        healthy: false,
        last_error: error,
        latency_ms: latency_ms ?? indexer.latency_ms,
      }),
  },
  {
    key: "delete",
    label: "Disable",
    destructive: true,
    applies: (indexer) => indexer.configured,
    call: (ids) => api.bulkDelete(ids),
    onOk: (sync, indexer) => sync.patch(indexer, REMOVED),
    onFail: () => {},
    confirm: (count) => ({
      title: `Disable ${count} ${count === 1 ? "Indexer" : "Indexers"}?`,
      message: "They won't be searched, and their settings will be cleared.",
      confirmLabel: "Disable",
      destructive: true,
    }),
  },
];

async function runAction(action, context, event) {
  const { selection, indexers, sync } = context;
  const byId = new Map(indexers().map((i) => [i.id, i]));
  const ids = [...selection.ids].filter((id) => {
    const indexer = byId.get(id);
    return indexer && action.applies(indexer);
  });
  if (!ids.length) return;
  if (action.confirm && !(await confirmDialog(action.confirm(ids.length)))) {
    return;
  }
  const settle = (outcome) => {
    const indexer = byId.get(outcome.id);
    sync.setTesting([outcome.id], false);
    if (outcome.status === "ok") action.onOk(sync, indexer, outcome);
    else action.onFail(sync, indexer, outcome);
  };
  const call = () => action.call(ids, settle).catch(() => null);
  let outcomes;
  if (action.streams) {
    // Each card's blinking dot shows progress; no spinner on the button.
    const button = event.currentTarget;
    sync.setTesting(ids, true);
    button.disabled = true;
    outcomes = await call();
    button.disabled = false;
  } else {
    outcomes = await withBusy(event.currentTarget, call);
  }
  sync.setTesting(ids, false);
  if (!outcomes) return;
  if (!action.streams) outcomes.forEach(settle);
  const failedIds = outcomes.filter((o) => o.status !== "ok").map((o) => o.id);
  if (!action.keepSelection) selection.replace(failedIds);
  if (action.key !== "delete") await sync.refreshConfigured();
}

// ---- bar ----

function actionButton(action, context, count) {
  return h(
    "button",
    {
      class: `bar-btn${action.destructive ? " danger" : ""}`,
      type: "button",
      disabled: count === 0,
      onclick: (event) => runAction(action, context, event),
    },
    action.label,
  );
}

// ---- navigation bar ----

/** The heading while selecting: "Select Items", then "N Selected". */
export function selectionTitle(selection) {
  const title = h("h1", {});
  const render = () => {
    const count = selection.ids.size;
    title.textContent = count ? `${count} Selected` : "Select Items";
  };
  selection.listen("title", render);
  render();
  return title;
}

/** Like Mail: "Select All" becomes "Deselect All" once all are chosen. */
export function selectAllButton(selection, visible) {
  const button = h("button", { class: "bar-btn", type: "button" });
  const allChosen = () => {
    const shown = visible();
    return shown.length > 0 && shown.every((i) => selection.has(i.id));
  };
  const render = () => {
    button.textContent = allChosen() ? "Deselect All" : "Select All";
  };
  button.addEventListener("click", () =>
    selection.replace(allChosen() ? [] : visible().map((i) => i.id)),
  );
  selection.listen("select-all", render);
  render();
  return button;
}

// ---- toolbar ----

/**
 * The action buttons; the caller decides where they sit (bottom capsule
 * on phones, top toolbar on iPad and Mac). `indexers` is every known
 * indexer, so selected cards hidden by filters still count.
 */
export function selectionActions({ selection, indexers, sync }) {
  const actions = h("div", { class: "selection-actions" });
  const context = { selection, indexers, sync };
  const render = () => {
    const chosen = indexers().filter((i) => selection.has(i.id));
    actions.replaceChildren(
      ...ACTIONS.map((action) =>
        actionButton(action, context, chosen.filter(action.applies).length),
      ),
    );
  };
  selection.listen("toolbar", render);
  render();
  return actions;
}
