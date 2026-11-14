// Recent searches, kept in this browser only.
const KEY = "jackett.recentSearches";
const LIMIT = 10;

// The same search is the same query run with the same dropdown picks.
const sameSearch = (a, b) =>
  a.query.trim().toLowerCase() === b.query.trim().toLowerCase() &&
  (a.trackers || "") === (b.trackers || "") &&
  (a.categories || "") === (b.categories || "");

function uniqueSearches(searches) {
  return searches.filter(
    (search, i) => searches.findIndex((s) => sameSearch(s, search)) === i,
  );
}

export function recentSearches() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || "[]");
    const valid = Array.isArray(saved)
      ? saved.filter((s) => typeof s?.query === "string")
      : [];
    return uniqueSearches(valid);
  } catch {
    return [];
  }
}

function store(searches) {
  try {
    localStorage.setItem(KEY, JSON.stringify(searches));
  } catch {
    // Private windows may refuse storage; history is a convenience only.
  }
}

export function rememberSearch(request) {
  if (!request.query.trim()) return;
  const others = recentSearches().filter((s) => !sameSearch(s, request));
  store([request, ...others].slice(0, LIMIT));
}

export function clearRecentSearches() {
  store([]);
}
