/**
 * Nexus Mind Graph — the workbench.
 *
 * ⭐ The graph is an engine; this is a workbench. The home surface is a ranked
 * list of next actions, not a canvas, and the Map is a secondary view.
 */
import { useEffect, useState } from "react";

import { ActionRow } from "./components/ActionRow";
import { CaptureBar } from "./components/CaptureBar";
import { ExplainPane } from "./components/ExplainPane";
import { Onboarding } from "./components/Onboarding";
import { ArtifactLoop } from "./components/ArtifactLoop";
import { ReviewQueue } from "./components/ReviewQueue";
import { SettingsPanel } from "./components/SettingsPanel";
import { DebugCompanion } from "./components/DebugCompanion";
import { MapView } from "./components/MapView";
import { Gallery } from "./components/Gallery";
import { EmptyState, ErrorState, LoadingState, PartialState } from "./components/SurfaceStates";
import { AnswerPane } from "./components/AnswerPane";
import { Dashboard } from "./components/Dashboard";
import { LogView } from "./components/LogView";
import { ShareView } from "./components/ShareView";
import { TensionCard } from "./components/TensionCard";
import { ApiError, getToken, probe, setToken, type Health } from "./lib/api";
import { useCompanion, useCalibration, useExplain, useFrontier, useQueryGraph, useStats, useTensions } from "./lib/hooks";
import { useUI } from "./lib/store";
import "./App.css";

function Health({ state, onRetry }: { state: Health | "unknown"; onRetry: () => void }) {
  const copy: Record<string, [string, string]> = {
    live: ["Live", "reading from the Graph API"],
    auth: ["Token needed", "backend is up — paste a role token"],
    down: ["No backend", "start it with scripts/serve_demo.py"],
    unknown: ["Checking", "…"],
  };
  const [l, d] = copy[state] ?? copy.unknown;
  return (
    <button className={`health health--${state}`} onClick={onRetry} title="Re-probe">
      <i /><b>{l}</b><span>{d}</span>
    </button>
  );
}

/** ⚠️ Capability refusals are shown, never swallowed — a 403 means the design
 *  is working, and hiding it makes the boundary invisible. */
function Refusal({ error }: { error: unknown }) {
  if (!(error instanceof ApiError)) return <ErrorState error={String(error)} onRetry={() => location.reload()} />;
  if (!error.isRefusal) return <ErrorState error={error.message} onRetry={() => location.reload()} />;
  return (
    <div className="refusal">
      <b>Not permitted with this token.</b>
      <span>{error.message}</span>
      <small>Capabilities are checked server-side. A client that could name its own would have none.</small>
    </div>
  );
}

export default function App() {
  const ui = useUI();
  const [health, setHealth] = useState<Health | "unknown">("unknown");
  const [onboarding, setOnboarding] = useState(false);
  const [settings, setSettings] = useState(false);
  const [debugCompanion, setDebugCompanion] = useState(false);
  const [predicting, setPredicting] = useState(false);
  const [ask, setAsk] = useState("");

  const check = () => probe().then(setHealth);
  useEffect(() => { check(); }, []);

  const stats = useStats();
  const frontier = useFrontier(5);
  const tensions = useTensions();
  const calibration = useCalibration();
  const explain = useExplain(ui.selected);
  const companion = useCompanion({ id: ui.selected ?? undefined });
  const hits = useQueryGraph(ask, ui.lens);

  useEffect(() => {
    const r = document.documentElement;
    r.toggleAttribute("data-contrast", ui.highContrast);
    r.toggleAttribute("data-reduced", ui.reducedMotion);
    r.toggleAttribute("data-cvd", ui.cvdSafe);
  }, [ui.highContrast, ui.reducedMotion, ui.cvdSafe]);

  if (onboarding) return <Onboarding onComplete={() => { setOnboarding(false); stats.refetch(); }} />;
  // ?gallery — the Phase 1 gate, kept out of the product shell on purpose.
  if (new URLSearchParams(location.search).has("gallery")) return <Gallery />;

  const live = health === "live";

  return (
    <div className="shell">
      <nav className="rail">
        <div className="brand">Mind Graph</div>
        {(["bench", "map", "sources", "log", "share"] as const).map((s) => (
          <button key={s} className={ui.surface === s ? "on" : ""} onClick={() => ui.set({ surface: s })}>
            {s[0].toUpperCase() + s.slice(1)}
          </button>
        ))}
        <div className="rail-foot">
          <button onClick={() => setOnboarding(true)}>+ New project</button>
          <button onClick={() => setSettings(!settings)}>Settings</button>
        </div>
      </nav>

      <main className="main">
        <header className="head">
          <div>
            <h1>Workbench</h1>
            <p>
              {live && stats.data
                ? `${stats.data.nodes} nodes · ${stats.data.established} established · ${stats.data.contested} contested`
                : "What to do next, what disagrees, and what you've proven."}
            </p>
          </div>
          <div className="head-a">
            <Health state={health} onRetry={check} />
            {health === "auth" && (
              <input
                className="tok"
                placeholder="paste role token"
                defaultValue={getToken() ?? ""}
                onKeyDown={(e) => {
                  if (e.key === "Enter") { setToken((e.target as HTMLInputElement).value.trim()); check(); }
                }}
              />
            )}
          </div>
        </header>

        <CaptureBar
          // ⚠️ Only fires for Question now — CaptureBar itself withholds the
          // call for every other type, since nothing else has a real backend
          // destination yet. See the fix note in CaptureBar.tsx.
          onSubmit={(q) => { ui.set({ surface: "bench" }); setAsk(q); }}
          /* ⚠️ The learning signal. A correction the system does not record is
             one the student pays for twice — and CORRECTION RATE, not routing
             accuracy, is the number F7 actually turns on. */
          onCorrect={(text, from, to) => {
            console.info("[capture] corrected", { text, from, to });
          }} />

        {settings && <SettingsPanel />}

        {!debugCompanion && (
          <button className="dc-fab" onClick={() => setDebugCompanion(true)}
            aria-label="Debug companion" title="Debug companion">?</button>
        )}
        {debugCompanion && <DebugCompanion onClose={() => setDebugCompanion(false)} />}

        {ui.surface === "bench" && (
          <>
            {ask.trim().length > 1 && (
              <section className="card">
                <div className="card-h"><h2>Ask</h2><span>{ask}</span></div>
                {/* ⭐ The turn is opt-in, under the free retrieval rather than
                    instead of it. Firing a paid multi-model turn on every
                    keystroke-completed question is how the cost envelope in
                    `Backend/09` Q2 stops meaning anything — and most questions
                    are answered by the traversal below. */}
                <AnswerPane question={ask} />
                <div className="card-h sub"><h3>Retrieved</h3><span>deterministic · free</span></div>
                {hits.isError && <Refusal error={hits.error} />}
                {hits.isLoading && <LoadingState>Retrieving…</LoadingState>}
                <ul className="hits">
                  {hits.data?.results.map((h) => (
                    <li key={h.id}>
                      <button onClick={() => ui.set({ selected: h.id, side: "explain" })}>
                        {h.label ?? h.id}
                      </button>
                      {/* ⭐ Every result carries its justified path — that is why
                          this is traversal and not a vector index. */}
                      <small>{h.hops}h · {h.path.length} step path</small>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="card">
              <div className="card-h"><h2>Now</h2><span>ranked by DOI</span></div>
              {frontier.isLoading && <LoadingState>Ranking…</LoadingState>}
              {frontier.isError && <Refusal error={frontier.error} />}
              {frontier.data?.actions.length === 0 && (
                <EmptyState message="Nothing ready — ingest something or record a measurement." actionText="New project" onAction={() => setOnboarding(true)} />
              )}
              {frontier.data?.actions.map((a) => (
                <ActionRow
                  key={a.id}
                  title={a.why}
                  meta={a.kind.toLowerCase()}
                  onClick={() => ui.set({ selected: a.id, side: "explain" })}
                />
              ))}
            </section>

            <section className="card">
              <div className="card-h"><h2>Disagreements</h2><span>{tensions.data?.tensions.length ?? 0} open</span></div>
              {tensions.isError && <Refusal error={tensions.error} />}
              {tensions.data?.tensions.length === 0 && (
                <EmptyState message="Nothing disagrees yet. It will." actionText="Ingest a paper" onAction={() => ui.set({ surface: "sources" })} />
              )}
              {tensions.data?.tensions.map((t, i) => (
                <TensionCard key={i} level={t.level} kind={t.kind} a={t.a} b={t.b} framing={t.framing} />
              ))}
            </section>

            <section className="card">
              <div className="card-h">
                <h2>Artifact</h2>
                <button onClick={() => setPredicting(!predicting)}>{predicting ? "Cancel" : "+ New prediction"}</button>
              </div>
              {predicting && (
                <ArtifactLoop
                  onRecorded={() => { stats.refetch(); calibration.refetch(); }}
                  calibration={calibration.data
                    ? { matched: calibration.data.matched, resolved: calibration.data.resolved }
                    : undefined} />
              )}
              {calibration.data && (
                <p className="cal">
                  {calibration.data.resolved >= 15
                    ? `${calibration.data.matched} of ${calibration.data.resolved} predictions correct.`
                    : `${calibration.data.resolved} resolved predictions — the reliability curve needs 15 before it means anything.`}
                </p>
              )}
            </section>
          </>
        )}

        {ui.surface === "map" && (
          <section className="card">
            <div className="card-h"><h2>Map</h2><span>secondary view · opened deliberately</span></div>
            {/* ⭐ Focused on the selection when there is one. The Map is opened
                FROM a question, not browsed — that is the whole reason a 50-node
                cap is navigable rather than restrictive. */}
            <MapView focus={ui.selected} />
          </section>
        )}

        {ui.surface === "sources" && <PartialState missingCount={1}>Sources reader is Phase 6.</PartialState>}

        {ui.surface === "log" && (
          <section className="card">
            <div className="card-h"><h2>Log</h2><span>a document, not a feed</span></div>
            <LogView onPredict={() => ui.set({ surface: "bench" })} />
          </section>
        )}

        {/* ⚠️ No frontier, no review, no capture bar reachable from here.
            Sharing is a different job from working, and a share page with an
            Accept button is a working surface that happens to be public. */}
        {ui.surface === "share" && (
          <section className="card">
            <div className="card-h"><h2>Share</h2><span>read-only · failures stay visible</span></div>
            <ShareView />
          </section>
        )}
      </main>

      <aside className="side">
        {/* ⭐ F2: a state dashboard, not a minimap — a shrunken hairball is
            still a hairball, and only we can render epistemic state. It sits
            above the context tabs because it answers the morning question
            ("where am I?") that the tabs assume you have already answered. */}
        <Dashboard bias={companion.data?.bias ?? []}
          onOpen={() => ui.set({ surface: "bench" })} />
        <div className="seg">
          {(["explain", "review", "sources"] as const).map((t) => (
            <button key={t} className={ui.side === t ? "on" : ""} onClick={() => ui.set({ side: t })}>{t}</button>
          ))}
        </div>
        {ui.side === "explain" && (
          ui.selected
            ? explain.isError
              ? <Refusal error={explain.error} />
              : explain.data && <ExplainPane data={explain.data} onPick={(id) => ui.set({ selected: id })} />
            : <EmptyState message="Select something to see why you believe it." actionText="Open the Bench" onAction={() => ui.set({ surface: "bench" })} />
        )}
        {ui.side === "review" && <ReviewQueue />}
        {ui.side === "sources" && <PartialState missingCount={1}>Ingest lands here.</PartialState>}
      </aside>
    </div>
  );
}
