// Multi-key sorting for the results list, chosen from a menu.
import { multiFilter } from "./multi-filter.js";

const DEFAULT = "publish_date:desc";

const SORTS = [
  ["seeders:desc", "Most Seeders"],
  ["grabs:desc", "Most Grabs"],
  ["size:desc", "Largest"],
  ["size:asc", "Smallest"],
  ["title:asc", "Title A–Z"],
  ["publish_date:desc", "Newest"],
  ["publish_date:asc", "Oldest"],
];

const keyOf = (value) => value.split(":")[0];
const orderOf = (value) => value.split(":")[1];

// A sort ranks by its column's place in the table, left to right, so the
// leftmost picked column decides first whatever order the picks were made in.
const columnRank = (columns) => (value) =>
  columns.findIndex((c) => c.key === keyOf(value));

// A column sorts one way at a time (its latest pick wins) and the picks
// are ranked by column position, not by the order they were made in.
function normalized(columns, values) {
  const rank = columnRank(columns);
  const latest = values.filter(
    (value, i) =>
      !values.slice(i + 1).some((later) => keyOf(later) === keyOf(value)),
  );
  return latest.sort((a, b) => rank(a) - rank(b));
}

const labelOf = (columns, value) => {
  const { label } = columns.find((c) => c.key === keyOf(value));
  return `${label}, ${orderOf(value) === "asc" ? "Ascending" : "Descending"}`;
};

// Header clicks can pick a sort the menu lacks; list it so it shows as set.
function menuOptions(columns, picked) {
  const rank = columnRank(columns);
  const extra = picked.filter(
    (value) => !SORTS.some(([known]) => known === value),
  );
  const extras = extra.map((v) => [v, labelOf(columns, v)]);
  return [...SORTS, ...extras].sort(([a], [b]) => rank(a) - rank(b));
}

// Compare by each picked column in rank order; the first difference decides.
function comparer(columns, values) {
  return (a, b) => {
    for (const value of values.length ? values : [DEFAULT]) {
      const { sort } = columns.find((c) => c.key === keyOf(value));
      const left = sort(a);
      const right = sort(b);
      const order = left < right ? -1 : left > right ? 1 : 0;
      if (order) return orderOf(value) === "desc" ? -order : order;
    }
    return 0;
  };
}

const flipped = (value) =>
  `${keyOf(value)}:${orderOf(value) === "desc" ? "asc" : "desc"}`;

/**
 * Sorts by every picked column, ranked by column position (the first is
 * the primary sort). `columns` carry `key`, `label` and `sort(release)`.
 */
export function createSorter(columns, onChange) {
  let values = [DEFAULT];
  const apply = (next) => {
    values = normalized(columns, next);
    menu.setOptions(menuOptions(columns, values));
    menu.setSelected(values);
    onChange();
  };
  const menu = multiFilter({
    all: "Sort",
    noun: "Sorts",
    options: menuOptions(columns, values),
    selected: values,
    onChange: () => apply(menu.list()),
  });
  const find = (key) => values.find((value) => keyOf(value) === key);

  // A plain header click sorts by that column alone; with `additive` it
  // joins (or flips within) the current sorts.
  const toggle = (key, additive) => {
    const current = find(key);
    const next = current ? flipped(current) : `${key}:desc`;
    if (!additive) return apply([next]);
    return apply(
      current
        ? values.map((v) => (v === current ? next : v))
        : [...values, next],
    );
  };

  return {
    menu: menu.root,
    compare: (a, b) => comparer(columns, values)(a, b),
    toggle,
    orderFor: (key) => (find(key) ? orderOf(find(key)) : null),
  };
}
