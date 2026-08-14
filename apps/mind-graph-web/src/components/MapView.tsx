/**
 * Phase 8 — the Map. `Frontend/01 §4.2`.
 *
 * ⭐ What this surface is FOR (settled 2026-08-12): the Map is a **storage and
 * browse mechanism**, not a planning tool. A student opens it to find what
 * they already know — a project's subgraph, a past decision, the thing they
 * saved in week 2 — not to decide what to do next. The Bench decides; the Map
 * remembers. Every choice below follows from that: it is seeded and scoped
 * rather than browsed whole, and finding beats surveying.
 *
 * ⚠️ Ranking happens SERVER-SIDE. This component had its own Degree-of-
 * Interest implementation for exactly one day, because the browser could not
 * run the real one. Two copies of a ranking function in two languages drift,
 * and the client's copy was strictly worse — `retrieve.rank` weighs six
 * components with weights that ramp as the graph ages, which a hand-rolled
 * degree score cannot express. The `map` route exists to delete that copy.
 *
 * ⚠️ No fisheye, no focus+context distortion. Distorting geometry to fit more
 * on screen trades a legible small graph for an illegible large one.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import Graph from "graphology";
import Sigma from "sigma";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { useQuery } from "@tanstack/react-query";

import { api, ApiError, type MapGraph } from "../lib/api";
import { cachePortable, rankPortable, readCachedPortable } from "../lib/frontier";
import { ErrorState, LoadingState } from "./SurfaceStates";
import "./MapView.css";

/**
 * ⚠️ BUG FIX, confirmed live: `/portable` — the whole reason for the §4.4
 * ranking split, and the thing that is supposed to make the frontier work at
 * a bench with no signal — had ZERO caller. `frontier.ts`'s cache/rank
 * functions were tested library code nobody invoked. This wires it in on two
 * ends: cache on every successful load, fall back to the cache when the live
 * fetch fails for a network reason (not a capability refusal).
 */
function portableToView(cached: NonNullable<ReturnType<typeof readCachedPortable>>): MapGraph {
  const ranked = rankPortable(cached);
  const nodes = ranked.map((r) => ({
    id: r.id, type: r.node.attributes.type, kind: r.node.attributes.kind,
    support: r.node.attributes.support, strength: r.node.attributes.strength,
    corroboration: r.node.attributes.corroboration,
    single_method: r.node.attributes.singleMethod,
    score: r.score, hops: r.node.attributes.hops, label: r.node.attributes.label,
  }));
  const keep = new Set(nodes.map((n) => n.id));
  const edges = cached.edges
    .filter((e) => keep.has(e.source) && keep.has(e.target))
    .map((e) => ({ src: e.source, dst: e.target, relation: e.attributes.relation }));
  return { nodes, edges, total: cached.attributes.nodeCount, held: 0,
           seeds: cached.attributes.seeds, cap: nodes.length };
}

/** Post-F4: hue is the FAMILY, the glyph is the type. Four hues, not six. */
const FAMILY: Record<string, string> = {
  Concept: "#7BF4FC", Question: "#7BF4FC",     // the lattice
  Claim: "#BB99FA", Note: "#BB99FA",           // your thinking
  Artifact: "#E5C14A",                         // your evidence
  Source: "#B79400",                           // outside evidence
};
const GLYPH: Record<string, string> = {
  Concept: "◆", Question: "?", Claim: "▲", Artifact: "■", Source: "▪", Note: "·",
};
/** VSUP — confidence desaturates toward grey, so grey cannot be a hue. */
const VSUP: Record<string, number> = {
  established: 1, corroborated: 0.85, tentative: 0.6, unknown: 0.38, unsupported: 0.22,
};

function mix(hex: string, k: number) {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const grey = 0.32 * r + 0.5 * g + 0.18 * b;
  const f = (c: number) => Math.round(c * k + grey * (1 - k));
  return `rgb(${f(r)},${f(g)},${f(b)})`;
}

export function MapView({ focus }: { focus?: string | null }) {
  const host = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ label: string; meta: string } | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["map", focus ?? null],
    queryFn: () => api.map(focus, 50),
    staleTime: 60_000,
    // ⚠️ offline is exactly the condition this component exists to survive —
    // retrying a dead network for 3 rounds before falling back defeats it.
    retry: (count, err) => !(err instanceof TypeError) && count < 2,
  });

  // Cache the full graph for offline re-ranking on every successful load.
  // Fire-and-forget: this must never block or fail the render.
  useEffect(() => {
    api.portable(null).then(cachePortable).catch(() => {});
  }, []);

  const [usingCache, setUsingCache] = useState(false);
  const view = useMemo(() => {
    if (data) { if (usingCache) setUsingCache(false); return data; }
    if (error && !(error instanceof ApiError && error.isRefusal)) {
      const cached = readCachedPortable();
      if (cached) { if (!usingCache) setUsingCache(true); return portableToView(cached); }
    }
    return null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, error]);

  useEffect(() => {
    if (!host.current || !view) return;
    const g = new Graph();
    for (const n of view.nodes) {
      const hue = FAMILY[n.type] ?? "#8FA9C9";
      g.addNode(n.id, {
        x: Math.random(), y: Math.random(),
        // ⭐ size carries DOI — the server's score — never raw degree. One
        // channel, one meaning.
        size: 4 + Math.min(8, Math.max(0, n.score) * 6),
        color: mix(hue, VSUP[n.strength] ?? VSUP[n.support] ?? 0.6),
        // the glyph is load-bearing after F4: it carries type, not decoration
        label: `${GLYPH[n.type] ?? "·"} ${n.label ?? n.id.slice(0, 8)}`,
        _meta: `${n.type} · ${n.support}${n.single_method ? " · single method" : ""}`,
      });
    }
    for (const e of view.edges) {
      if (!g.hasNode(e.src) || !g.hasNode(e.dst) || g.hasEdge(e.src, e.dst)) continue;
      g.addEdge(e.src, e.dst, {
        size: 1,
        // cool supports, warm contradicts — the one place hue is not type
        color: e.relation === "contradicts" ? "#E4756B"
          : e.relation === "supports" ? "#7EC8C0" : "#3A4048",
      });
    }
    if (g.order > 2) forceAtlas2.assign(g, { settings: forceAtlas2.inferSettings(g), iterations: 220 });

    /* ⭐ F5, settled by measurement (`scripts/f5_layout.ts`). Hue carries type,
       so project membership has to live on position — but ForceAtlas2 clusters
       by connectivity, not by project. Measured silhouette over 4 projects:

           cross-project edges     bare      with grouping
           5%                      0.571     0.881
           15%                     0.494     0.852
           30%                     0.354     0.802

       ⚠️ Bare layout degrades exactly as cross-project links grow — and those
       links are the most valuable thing in the product (crossover detection),
       so the configuration that fails is the one real data produces. A light
       centroid pull fixes it and costs one pass.

       ⚠️ Deliberately weak (0.02). Strong grouping makes pretty circles that
       lie about topology — the point is legible regions, not a pie chart. */
    const projects = new Map<string, string>();
    g.forEachNode((id) => {
      const p = view.nodes.find((n) => n.id === id)?.kind ?? "";
      if (p) projects.set(id, p);
    });
    if (projects.size > 1) {
      const STRENGTH = 0.02;
      for (let round = 0; round < 60; round++) {
        const cx = new Map<string, [number, number, number]>();
        g.forEachNode((id, a) => {
          const p = projects.get(id); if (!p) return;
          const c = cx.get(p) ?? [0, 0, 0];
          cx.set(p, [c[0] + (a.x as number), c[1] + (a.y as number), c[2] + 1]);
        });
        g.forEachNode((id, a) => {
          const p = projects.get(id); if (!p) return;
          const c = cx.get(p); if (!c) return;
          g.setNodeAttribute(id, "x", (a.x as number) + (c[0] / c[2] - (a.x as number)) * STRENGTH);
          g.setNodeAttribute(id, "y", (a.y as number) + (c[1] / c[2] - (a.y as number)) * STRENGTH);
        });
      }
    }

    const sig = new Sigma(g, host.current, { renderEdgeLabels: false, defaultEdgeType: "line" });
    sig.on("enterNode", ({ node }) => {
      const a = g.getNodeAttributes(node) as Record<string, string>;
      setHover({ label: a.label, meta: a._meta });
    });
    sig.on("leaveNode", () => setHover(null));
    sig.getCamera().on("updated", () => setHover(null));

    // ⚠️ The cleanup belongs HERE, not inside a timer callback — a cleanup
    // returned from a setTimeout is never called, and every remount leaks a
    // WebGL context until the tab dies. That was the previous version's bug.
    return () => { sig.kill(); g.clear(); };
  }, [view]);

  if (isLoading) return <LoadingState><div className="map-skel" /></LoadingState>;
  if (error && !view) {
    const e = error as ApiError;
    // ⚠️ No cache to fall back on either — say that specifically, not just
    // "did not load", since the honest reason here is "never been online".
    const noCache = !(e instanceof ApiError && e.isRefusal);
    return (
      <ErrorState
        error={e.isRefusal ? "This role cannot read the graph."
          : noCache ? "The map did not load, and there is no cached graph to fall back on yet — open the Map once while online."
          : `The map did not load — ${e.message}`}
        stillWorks="The Bench, the log and your predictions are unaffected."
        onRetry={e.isRefusal ? undefined : () => location.reload()}
      />
    );
  }

  return (
    <div className="map">
      {usingCache && (
        // ⚠️ Must not look like the live view. Offline data is real but stale,
        // and a Map that can't tell you which one you're looking at is worse
        // than one that admits it's disconnected (F07 §1 — the `stale` state).
        <div className="map-offline">⚠ offline — showing the last cached graph, ranked locally</div>
      )}
      <div className="map-bar">
        {/* ⚠️ Say what was held back. A capped view that reports only what it
            drew is claiming the graph IS 50 nodes. */}
        {view && view.held > 0
          ? <span>showing the top <b>{view.nodes.length}</b> of {view.total} by relevance{focus ? " to your selection" : ""}</span>
          : <span>showing all <b>{view?.nodes.length ?? 0}</b> nodes</span>}
        <span className="map-note">ranked by the same DOI the Bench uses</span>
      </div>
      <div ref={host} className="map-canvas" />
      {hover && (
        <div className="map-tip">
          <b>{hover.label}</b>
          <span>{hover.meta}</span>
        </div>
      )}
    </div>
  );
}
