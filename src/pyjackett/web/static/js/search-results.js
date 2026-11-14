// Results view of a manual search, reached from the Search form.
import { api } from "./api.js";
import { clear, h } from "./dom.js";
import { spinner, symbol } from "./icons.js";
import { mountResultsList } from "./results-list.js";
import { recall, remember } from "./stale-cache.js";

// As in iOS navigation bars: a chevron and the title of the previous view.
function backLink() {
  return h(
    "a",
    { class: "back-link", href: "#search" },
    symbol("chevron.left", 18, 2.4),
    "Search",
  );
}

/** Key of a finished search in the client cache. */
export function searchKey(request) {
  const { query, trackers, categories } = request;
  return `search:${JSON.stringify([query, trackers, categories])}`;
}

// A stored search is good for as long as the server keeps its own results.
async function cachedReleases(request) {
  const stored = recall(searchKey(request));
  if (!stored) return null;
  const config = await api.serverConfig();
  const age = (Date.now() - stored.at) / 1000;
  return config.cache_enabled && age < config.cache_ttl
    ? stored.releases
    : null;
}

async function streamResults(
  request,
  apiKey,
  { list, loading, progress, backRow, collected, controller },
) {
  const params = {
    query: request.query,
    "Tracker[]": request.trackers,
    "Category[]": request.categories,
  };
  const onIndexer = ({ results }) => {
    // The page was replaced (e.g. back to the form): stop feeding it.
    if (!backRow.isConnected) return controller.abort();
    loading.remove();
    collected.push(...results);
    list.add(results);
    // The small spinner says "more is coming" once there is something shown.
    if (collected.length) backRow.append(progress);
  };
  try {
    await api.searchStream(apiKey, params, onIndexer, controller.signal);
    // Only a search that ran to the end is worth showing again.
    remember(searchKey(request), { at: Date.now(), releases: collected });
  } finally {
    loading.remove();
    progress.remove();
    list.finish();
  }
}

// The search shown in each pane, so a tab switch comes back to it as it
// was (still streaming or finished) instead of running the search again.
const running = new WeakMap();

function resumeRunning(view, key) {
  const search = running.get(view);
  if (search?.key !== key || !view.contains(search.host)) return false;
  search.list.refresh();
  return true;
}

export async function renderSearchResults(view, state) {
  const request = state.search;
  const key = searchKey(request);
  if (resumeRunning(view, key)) return;
  const filterHost = h("div", { class: "results-filter" });
  const listHost = h("div", {});
  const loading = h("div", { class: "empty" }, spinner(28));
  // Joins the back row with the first results and stays until the end.
  const progress = spinner(20);
  const backRow = h("div", { class: "back-row" }, backLink());
  const cached = await cachedReleases(request);
  clear(view).append(
    backRow,
    h("div", { class: "view-head" }, h("h1", {}, request.query), filterHost),
    listHost,
    cached ? null : loading,
  );
  const collected = cached ?? [];
  const list = mountResultsList(listHost, [...collected], filterHost);
  const controller = new AbortController();
  running.get(view)?.stop();
  running.set(view, {
    key,
    host: listHost,
    list,
    stop: () => controller.abort(),
  });
  if (cached) {
    list.finish();
    return;
  }
  await streamResults(request, state.apiKey, {
    list,
    loading,
    progress,
    backRow,
    collected,
    controller,
  }).catch(() => {});
}
