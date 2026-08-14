/**
 * The Phase 1 gate: every state of every primitive on one page.
 *
 * ⭐ This exists so the encoding can be checked as a system rather than one
 * component at a time. Most encoding bugs are collisions — two channels
 * quietly carrying the same thing — and a collision is invisible until you see
 * the whole matrix at once.
 */
import { useState } from 'react';

import { NodeChip, type ConfidenceLevel, type NodeType, type SupportState } from './NodeChip';
import { EmptyState, ErrorState, LoadingState, PartialState, StaleState } from './SurfaceStates';
import { useUI } from '../lib/store';

const TYPES: NodeType[] = ['concept', 'question', 'claim', 'artifact', 'source', 'note'];
const CONF: ConfidenceLevel[] = ['1_00', '0_85', '0_75', '0_65', '0_55', 'amb'];
const SUPPORT: SupportState[] = ['supported', 'tentative', 'unsupported', 'contested', 'phantom'];

const FAMILY: Record<NodeType, string> = {
  concept: 'lattice', question: 'lattice',
  claim: 'thinking', note: 'thinking',
  artifact: 'yours', source: 'outside',
};

export function Gallery() {
  const ui = useUI();
  const [zoom, setZoom] = useState(1);

  return (
    <div className="gallery">
      <header>
        <h1>Component gallery</h1>
        <p>
          Phase 1 gate. ⭐ Hue carries <b>family</b>, the glyph carries <b>type</b>,
          chroma carries <b>confidence</b>, fill carries <b>support</b>. If any two of
          those ever encode the same thing, it will show here first.
        </p>
        <div className="controls">
          <label><input type="checkbox" checked={ui.highContrast}
            onChange={(e) => ui.set({ highContrast: e.target.checked })} /> High contrast</label>
          <label><input type="checkbox" checked={ui.reducedMotion}
            onChange={(e) => ui.set({ reducedMotion: e.target.checked })} /> Reduced motion</label>
          <label><input type="checkbox" checked={ui.cvdSafe}
            onChange={(e) => ui.set({ cvdSafe: e.target.checked })} /> CVD-safe</label>
          <label>
            Zoom
            <input type="range" min="0.75" max="2" step="0.25" value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))} />
            {zoom}×
          </label>
        </div>
      </header>

      <section style={{ zoom }}>
        <h2>Type × confidence</h2>
        <p className="note">
          ⚠️ Read the bottom row. At <code>AMBIGUOUS</code> the hues are nearly grey —
          which is the point of VSUP, and the reason grey is not available as a
          type colour.
        </p>
        <table className="matrix">
          <thead>
            <tr><th /><th>1.00</th><th>0.85</th><th>0.75</th><th>0.65</th><th>0.55</th><th>amb</th></tr>
          </thead>
          <tbody>
            {TYPES.map((t) => (
              <tr key={t}>
                <th>{t}<small>{FAMILY[t]}</small></th>
                {CONF.map((c) => (
                  <td key={c}><NodeChip label={t} type={t} confidence={c} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section style={{ zoom }}>
        <h2>Type × support</h2>
        <table className="matrix">
          <thead>
            <tr><th />{SUPPORT.map((s) => <th key={s}>{s}</th>)}</tr>
          </thead>
          <tbody>
            {TYPES.map((t) => (
              <tr key={t}>
                <th>{t}</th>
                {SUPPORT.map((s) => (
                  <td key={s}><NodeChip label={t} type={t} supportState={s} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section style={{ zoom }}>
        <h2>Rim glyphs</h2>
        <p className="note">⚠️ Full at three. A fourth competes for one of these, never joins them.</p>
        <div className="row">
          <NodeChip label="one method" type="claim" rimGlyphs={['single-method']} />
          <NodeChip label="contested" type="claim" supportState="contested" rimGlyphs={['contested']} />
          <NodeChip label="stale" type="claim" rimGlyphs={['stale']} />
          <NodeChip label="all three" type="claim" supportState="contested"
            rimGlyphs={['single-method', 'contested', 'stale']} />
        </div>
      </section>

      <section>
        <h2>The five states</h2>
        <p className="note">
          ⭐ <code>partial</code> is the one that matters — an async analyzer makes it
          the normal case, and it has to look deliberate rather than half-broken.
        </p>
        <div className="states">
          <EmptyState message="Nothing here yet." actionText="Add a source" onAction={() => {}} />
          <LoadingState>Ranking…</LoadingState>
          <PartialState missingCount={38}>12 of 50 nodes retrieved</PartialState>
          <ErrorState error="frontier 503 — the analyzer is behind" onRetry={() => {}} />
          <StaleState age="4 h" onRefresh={() => {}}>Communities last computed at 03:00</StaleState>
        </div>
      </section>
    </div>
  );
}
