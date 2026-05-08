export type HasEventFingerprint = {
  title: string;
  venue: string;
  start_time: string;
};

export function dedupeByEventFingerprint<T extends HasEventFingerprint>(rows: T[]): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const r of rows) {
    const k = `${r.title}@@${r.start_time}@@${r.venue}`;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(r);
  }
  return out;
}

