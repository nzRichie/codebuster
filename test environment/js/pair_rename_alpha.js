/**
 * Count distinct values — variable names tuned for plagiarism testing (rename pair A).
 */

function uniqueCount(entries) {
  const seen = new Set();
  for (const entry of entries) {
    seen.add(entry);
  }
  return seen.size;
}

export default uniqueCount;
