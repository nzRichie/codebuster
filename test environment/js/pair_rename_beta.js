/**
 * Count distinct values — same logic as pair_rename_alpha.js with renamed identifiers (rename pair B).
 */

function distinctTotal(items) {
  const known = new Set();
  for (const item of items) {
    known.add(item);
  }
  return known.size;
}

export default distinctTotal;
