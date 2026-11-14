// Standard Torznab categories offered by the configured indexers.
const CUSTOM_CATEGORY_START = 100000;

export function standardCategories(indexers) {
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
