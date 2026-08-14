/**
 * F5 — do project regions hold under force layout, or produce incoherent blobs?
 *
 *     npm run f5
 *
 * The doubt: hue carries node TYPE, so project membership has to live on
 * position. But ForceAtlas2 clusters by connectivity, not by project — so if a
 * project's nodes are not connectivity-adjacent, "spatial regions" produces
 * overlapping mush and the encoding silently fails.
 *
 * ⚠️ This is a MEASUREMENT, not a screenshot. "Looks clustered" is exactly the
 * judgement a person makes badly, and the failure mode is gradual — regions
 * that mostly hold with a few strays read as fine and are not.
 *
 * The metric is **silhouette score** over 2-D positions with project as the
 * label: +1 every node sits with its own project, 0 means the regions are
 * indistinguishable, negative means nodes are closer to another project's
 * centre than their own.
 */
import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";

type Node = { id: string; project: string };

/** Multi-project graph with realistic cross-project links. */
function build(projects: number, perProject: number, crossRate: number, seed = 7) {
  let s = seed;
  const rnd = () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296;

  const g = new Graph({ type: "undirected" });
  const nodes: Node[] = [];
  for (let p = 0; p < projects; p++) {
    const proj = `p${p}`;
    for (let i = 0; i < perProject; i++) {
      const id = `${proj}-n${i}`;
      g.addNode(id, { project: proj, x: rnd(), y: rnd() });
      nodes.push({ id, project: proj });
    }
  }
  // within-project structure: a hub plus local links
  for (let p = 0; p < projects; p++) {
    const hub = `p${p}-n0`;
    for (let i = 1; i < perProject; i++) {
      if (rnd() < 0.55) g.mergeEdge(hub, `p${p}-n${i}`);
      const j = 1 + Math.floor(rnd() * (perProject - 1));
      if (j !== i) g.mergeEdge(`p${p}-n${i}`, `p${p}-n${j}`);
    }
  }
  // ⭐ cross-project edges are the whole difficulty. They are also the most
  // valuable thing in the product (crossover detection), so a layout that
  // only works without them is no use.
  const all = nodes.map((n) => n.id);
  const crossCount = Math.round(all.length * crossRate);
  for (let i = 0; i < crossCount; i++) {
    const a = all[Math.floor(rnd() * all.length)];
    const b = all[Math.floor(rnd() * all.length)];
    if (a !== b && g.getNodeAttribute(a, "project") !== g.getNodeAttribute(b, "project")) {
      g.mergeEdge(a, b);
    }
  }
  return g;
}

/** Mean silhouette over 2-D positions, labelled by project. */
function silhouette(g: Graph): number {
  const pts = g.mapNodes((id, a) => ({ id, p: a.project as string, x: a.x as number, y: a.y as number }));
  const byProj = new Map<string, typeof pts>();
  for (const q of pts) {
    const l = byProj.get(q.p); if (l) l.push(q); else byProj.set(q.p, [q]);
  }
  const d = (a: typeof pts[0], b: typeof pts[0]) => Math.hypot(a.x - b.x, a.y - b.y);
  let total = 0;
  for (const q of pts) {
    const own = byProj.get(q.p)!;
    const a = own.length < 2 ? 0
      : own.reduce((s, o) => s + (o.id === q.id ? 0 : d(q, o)), 0) / (own.length - 1);
    let b = Infinity;
    for (const [proj, group] of byProj) {
      if (proj === q.p) continue;
      b = Math.min(b, group.reduce((s, o) => s + d(q, o), 0) / group.length);
    }
    total += (b - a) / Math.max(a, b);
  }
  return total / pts.length;
}

/** A grouping force: pull each node toward its project's centroid. */
function applyGrouping(g: Graph, strength: number, rounds = 60) {
  for (let r = 0; r < rounds; r++) {
    const cx = new Map<string, [number, number, number]>();
    g.forEachNode((_, a) => {
      const p = a.project as string;
      const c = cx.get(p) ?? [0, 0, 0];
      cx.set(p, [c[0] + (a.x as number), c[1] + (a.y as number), c[2] + 1]);
    });
    g.forEachNode((id, a) => {
      const [sx, sy, n] = cx.get(a.project as string)!;
      g.setNodeAttribute(id, "x", (a.x as number) + ((sx / n) - (a.x as number)) * strength);
      g.setNodeAttribute(id, "y", (a.y as number) + ((sy / n) - (a.y as number)) * strength);
    });
  }
}

function run(label: string, crossRate: number, grouping: number) {
  const g = build(4, 30, crossRate);
  forceAtlas2.assign(g, { settings: forceAtlas2.inferSettings(g), iterations: 300 });
  if (grouping > 0) applyGrouping(g, grouping);
  const s = silhouette(g);
  const verdict = s >= 0.5 ? "HOLDS" : s >= 0.25 ? "weak" : "FAILS";
  console.log(
    `  ${label.padEnd(34)} silhouette ${s.toFixed(3).padStart(7)}   ${verdict}`);
  return s;
}

console.log("\nF5 — do project regions survive force layout?");
console.log("  4 projects × 30 nodes. silhouette: ≥0.5 holds, <0.25 fails.\n");

console.log("  ── no grouping force (what MapView does today) ──");
const bare = [run("5% cross-project edges", 0.05, 0),
              run("15% cross-project edges", 0.15, 0),
              run("30% cross-project edges", 0.30, 0)];

console.log("\n  ── with a grouping force ──");
const grouped = [run("5% cross, grouping 0.02", 0.05, 0.02),
                 run("15% cross, grouping 0.02", 0.15, 0.02),
                 run("30% cross, grouping 0.02", 0.30, 0.02),
                 run("30% cross, grouping 0.05", 0.30, 0.05)];

const worstBare = Math.min(...bare);
const worstGrouped = Math.min(...grouped.slice(0, 3));
console.log(`\n  worst without grouping: ${worstBare.toFixed(3)}`);
console.log(`  worst with grouping:    ${worstGrouped.toFixed(3)}`);
console.log(worstBare >= 0.5
  ? "\n  ⭐ Regions hold unaided — no grouping force needed.\n"
  : worstGrouped >= 0.5
    ? "\n  ⚠️ Regions need a grouping force. Without one the encoding fails\n" +
      "     silently at realistic cross-project density.\n"
    : "\n  ⚠️ Regions do not hold even with grouping — project must move OFF\n" +
      "     position onto another channel, or the Map scopes to one project.\n");
