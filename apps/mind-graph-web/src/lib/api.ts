/**
 * The Graph API client. Backend/05 §8.
 *
 * ⭐ Capabilities are enforced server-side. This client does not know what it
 * is allowed to do — it asks and handles the refusal, which is the only
 * arrangement that cannot be bypassed by editing the frontend.
 */

export type Bundle = "reader" | "grounder" | "critic" | "human";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
  /** 403 is a capability refusal and must be shown, not swallowed. */
  get isRefusal() { return this.status === 403; }
}

export interface Stats {
  nodes: number; edges: number; established: number; contested: number;
  single_method: number; dead_ends: number; last_seq: number;
}
export interface Action { id: string; kind: string; why: string; priority: number; }
export interface Tension { a: string; b: string; kind: string; level: string; framing: string; }
export interface Explain {
  id: string; type: string; kind: string | null; support: string; strength: string;
  corroboration: number; single_method: boolean;
  supported_by: string[]; contradicted_by: string[];
  /** ⭐ A claim that LOST its evidence is not one that never had any. */
  retracted_support: string[];
}
export interface QueryHit { id: string; score: number; hops: number; path: string[]; label?: string; }
/** The project document, and what Share publishes. */
export interface LogEntry {
  seq: number; ts: string; type: string; ids: string[];
  /** ⚠️ empty when the token lacks READ_CONTENT — shape without words. */
  labels: string[];
  retracted: boolean;
}
export interface Artifact {
  id: string; label: string | null; kind: string | null;
  predicted: { low: number; high: number; unit: string; quantity?: string } | null;
  measured: { value: number | null; unit: string } | null;
  agreement: "matched" | "diverged" | "inconclusive" | "not_run";
  supports: string[];
}
export interface Log {
  entries: LogEntry[];
  artifacts: Artifact[];
  /** ⭐ The hash is what makes the page a record rather than a claim. */
  head: { seq: number; hash: string; verified: boolean };
}
/** The Map's subgraph — already ranked and capped by the server. */
export interface MapNode {
  id: string; type: string; kind: string | null;
  support: string; strength: string;
  corroboration: number; single_method: boolean;
  score: number; hops: number | null; label?: string;
}
export interface MapGraph {
  nodes: MapNode[];
  edges: Array<{ src: string; dst: string; relation: string }>;
  total: number; held: number; seeds: string[]; cap: number;
}
/** The companion's four supervisor moves. `companion.py` */
export interface Bias {
  quantity: string; n: number; matched: number;
  direction: "optimistic" | "pessimistic" | "calibrated";
  median_error: number | null; advice: string;
}
export interface Companion {
  bias: Bias[];
  transfer: Array<{ a: string; b: string; a_project: string; b_project: string; overlap: number; shared: string[] }>;
  recall?: Array<{ id: string; label: string; reason: string; overlap: number; kind: string }>;
  impact?: { id: string; direct: string[]; cascade: string[]; unsupported_after: string[]; load_bearing: boolean };
}
export interface Calibration {
  resolved: number; matched: number; diverged: number;
  hit_rate: number | null; inconclusive: number;
}

const BASE = import.meta.env.VITE_API ?? "http://127.0.0.1:8787";

let token: string | null = localStorage.getItem("mg_token");
export const setToken = (t: string | null) => {
  token = t;
  if (t) localStorage.setItem("mg_token", t); else localStorage.removeItem("mg_token");
};
export const getToken = () => token;

async function call<T>(route: string, opts: { params?: Record<string, unknown>; body?: unknown } = {}): Promise<T> {
  const qs = opts.params
    ? "?" + new URLSearchParams(
        Object.entries(opts.params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]))
    : "";
  const res = await fetch(`${BASE}/${route}${qs}`, {
    method: opts.body ? "POST" : "GET",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token ?? ""}` },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).error ?? msg; } catch { /* body was not JSON */ }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  stats: () => call<Stats>("stats"),
  frontier: (k = 3) => call<{ actions: Action[] }>("frontier", { params: { k } }),
  tensions: () => call<{ tensions: Tension[] }>("contradictions"),
  explain: (id: string) => call<Explain>("explain", { params: { id } }),
  /** ⚠️ Needs READ_CONTENT — seeding matches labels, and labels are user text. */
  query: (q: string, lens?: string, k = 25) => call<{ results: QueryHit[] }>("query", { params: { q, lens, k } }),
  neighbors: (id: string, hops = 1) => call<{ nodes: string[] }>("neighbors", { params: { id, hops } }),
  review: () => call<{ pending: Array<Record<string, unknown>> }>("review"),
  decide: (ids: string[], accept: boolean) => call<{ decided: number }>("decide", { body: { ids, accept } }),
  calibration: () => call<Calibration>("calibration"),
  analyze: () => call<Record<string, unknown>>("analyze"),
  resurrections: () => call<{ resurrected: Array<Record<string, unknown>> }>("resurrections"),
  nudge: () => call<{ triggered: boolean; ratio: number; outstanding: number; reason: string }>("nudge"),
  timeline: (at: number) => call<{ nodes: number; edges: number; at: number }>("timeline", { params: { at } }),
  exportGraph: () => call<Record<string, unknown>>("export"),
  /** ⚠️ Needs READ_TIMELINE. Order is the point — a log without it is a list. */
  log: () => call<Log>("log"),
  /** ⭐ Not a model call — graph and arithmetic over the student's own
   *  outcomes, which is why nobody else can compute it. */
  companion: (opts: { id?: string; q?: string } = {}) =>
    call<Companion>("companion", { params: opts }),
  /** ⭐ Ranked SERVER-SIDE. The client used to rank a raw export itself, which
   *  meant two Degree-of-Interest implementations that could disagree — and
   *  the client's was the worse one, missing the six weighted components. */
  map: (focus?: string | null, k = 50) =>
    call<MapGraph>("map", { params: { focus: focus ?? undefined, k } }),
  /**
   * ⚠️ BUG FIX, confirmed live: this method did not exist. The backend route
   * (`mindgraph/api.py:_portable`) and the client ranking logic
   * (`lib/frontier.ts`) were both built and tested — nobody wired a typed
   * call between them, so the offline frontier — the whole point of the
   * §4.4 ranking split — had no way to ever run. `k` defaults high because
   * this payload is meant to be CACHED and re-ranked locally, not capped for
   * one screen the way `/map` is. ⚠️ No `k` param — the backend route
   * (`_portable`) returns the full expanded graph uncapped; inventing a
   * client-side cap parameter the server doesn't honor would be its own
   * small lie.
   */
  portable: (focus?: string | null) =>
    call<import("./frontier").Portable>("portable", { params: { focus: focus ?? undefined } }),
  /** ⭐ The main verb. 503 when no model endpoint is configured, and that
   *  refusal is shown, never smoothed into a keyword search. */
  turn: (question: string, k = 12) =>
    call<Turn>("turn", { body: { question, k } }),
  /** ⭐ Human-only. The record of what worked must not be writable by AI. */
  predict: (b: { label: string; quantity: string; low: number; high: number; unit: string; supports?: string[]; method?: string }) =>
    call<Record<string, unknown>>("predict", { body: b }),
  validate: (b: { artifact_id: string; value: number | null; unit?: string }) =>
    call<Record<string, unknown>>("validate", { body: b }),
  start: (question: string, transcript = "") =>
    call<Record<string, unknown>>("start", { body: { question, transcript } }),
};

export interface Turn {
  question: string; answer: string; seeds: string[];
  proposals: Array<Record<string, unknown>>;
  critique: Array<Record<string, unknown>>;
  /** ⭐ Rejections are part of the reply. A turn that discarded four
   *  proposals and says nothing looks like one that found four. */
  rejected: Array<{ reason: string; item: Record<string, unknown> }>;
  role_calls: string[]; escalated: boolean; degraded: boolean;
  cost: { usd: number; accepted: number; usd_per_accepted: number | null;
          by_tier: Record<string, number> };
}

export type Health = "live" | "auth" | "down";

/** ⚠️ Four states, never a silent fallback. A UI that claims to be live when
 *  it is not is worse than one that admits it is showing nothing. */
export async function probe(): Promise<Health> {
  try {
    const res = await fetch(`${BASE}/stats`, { headers: { Authorization: `Bearer ${token ?? ""}` } });
    if (res.status === 401) return "auth";
    return res.ok ? "live" : "down";
  } catch { return "down"; }
}
