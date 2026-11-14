// Stale-while-revalidate: show the last answer at once, refresh behind it.
export const CONFIGURED_KEY = "indexers:configured";
export const ALL_KEY = "indexers:all";

const store = new Map();

export function remember(key, value) {
  store.set(key, value);
}

export function recall(key) {
  return store.get(key);
}

export function invalidate(key) {
  store.delete(key);
}

export async function loadStale(key, fetcher, onFresh) {
  const hadValue = store.has(key);
  const previous = store.get(key);
  const pending = fetcher().then((value) => {
    store.set(key, value);
    return value;
  });
  if (!hadValue) return pending;
  pending
    .then((value) => {
      const changed = JSON.stringify(value) !== JSON.stringify(previous);
      if (changed && onFresh) onFresh(value);
    })
    .catch(() => {});
  return previous;
}
