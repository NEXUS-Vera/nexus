/**
 * Cross-runtime conformance — does the browser rank exactly like the server?
 *
 *     npm run conformance
 *
 * ⭐ This is the guard that makes the §4.4 split safe. The backend generates a
 * fixture (`Backend_build/scripts/gen_conformance.py`) containing a real
 * portable payload and the ranking Python produces from it. This runs the
 * TypeScript ranking on the same payload and demands identical output — same
 * order, same scores.
 *
 * ⚠️ A failure here is not a test being fussy. It means the Map is about to
 * rank differently from the Bench, which is the exact bug that made us stop
 * ranking in the client in the first place — and the kind nobody notices until
 * a student says "why is this at the top".
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { hopsFrom, rankPortable, type Portable } from "../src/lib/frontier.ts";

const FIXTURE = join(import.meta.dirname, "..", "src", "lib", "__fixtures__", "conformance.json");

function main(): number {
  const raw = JSON.parse(readFileSync(FIXTURE, "utf8")) as {
    payload: Portable;
    expected: Array<{ id: string; score: number }>;
  };

  const got = rankPortable(raw.payload);
  const want = raw.expected;
  const fails: string[] = [];

  if (got.length !== want.length) {
    fails.push(`length: got ${got.length}, want ${want.length}`);
  }
  for (let i = 0; i < Math.min(got.length, want.length); i++) {
    if (got[i].id !== want[i].id) {
      fails.push(`#${i} order: got ${got[i].id.slice(0, 8)}…, want ${want[i].id.slice(0, 8)}…`);
    } else if (Math.abs(got[i].score - want[i].score) > 1e-5) {
      fails.push(`#${i} score ${got[i].id.slice(0, 8)}…: got ${got[i].score}, want ${want[i].score}`);
    }
  }

  // ⭐ Re-seeding must also agree in SHAPE — the client computes its own hops
  // when the focus changes, and a distance function that disagrees produces a
  // ranking that is individually plausible and collectively wrong.
  const seeds = raw.payload.attributes.seeds;
  if (seeds.length) {
    const hops = hopsFrom(raw.payload, seeds);
    for (const n of raw.payload.nodes) {
      const server = n.attributes.hops;
      const client = hops.get(n.key)!;
      if (server !== client) {
        fails.push(`hops ${n.key.slice(0, 8)}…: server ${server}, client ${client}`);
      }
    }
  }

  if (fails.length) {
    console.error(`\n  ✗ CONFORMANCE FAILED — ${fails.length} mismatch(es)\n`);
    for (const f of fails.slice(0, 12)) console.error(`      ${f}`);
    if (fails.length > 12) console.error(`      … and ${fails.length - 12} more`);
    console.error(
      "\n  The client and server disagree about ranking. Either the arithmetic\n" +
      "  in src/lib/frontier.ts drifted from mindgraph/portable.py, or the\n" +
      "  fixture is stale — regenerate it with:\n" +
      "      python3 ../Backend_build/scripts/gen_conformance.py\n");
    return 1;
  }

  console.log(`\n  ✓ conformance — ${got.length} nodes rank identically in both runtimes`);
  console.log(`    top: ${got[0].id.slice(0, 8)}… ${got[0].score}`);
  console.log(`    hop distances agree on all ${raw.payload.nodes.length} nodes\n`);
  return 0;
}

process.exit(main());
