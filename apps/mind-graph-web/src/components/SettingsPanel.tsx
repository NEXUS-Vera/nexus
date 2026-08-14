/**
 * Settings. Frontend/07 §3 — small, and mostly about trust.
 */
import { api } from '../lib/api';
import { useUI } from '../lib/store';
import './SettingsPanel.css';

export function SettingsPanel() {
  const ui = useUI();

  const toggle = (k: 'reducedMotion' | 'highContrast' | 'cvdSafe', label: string, desc: string) => (
    <div className="set-row" key={k}>
      <div>
        <div className="k">{label}</div>
        <div className="d">{desc}</div>
      </div>
      <button className={`tog${ui[k] ? ' on' : ''}`} onClick={() => ui.set({ [k]: !ui[k] } as never)}
        aria-pressed={ui[k]} aria-label={label}><i /></button>
    </div>
  );

  const exportGraph = async () => {
    const blob = new Blob([JSON.stringify(await api.exportGraph(), null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'mindgraph.json';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <section className="settings">
      <h3>Accessibility</h3>
      {toggle('reducedMotion', 'Reduced motion', 'Staged transitions become instant.')}
      {toggle('highContrast', 'High contrast', 'Raises every contrast floor. ⚠️ It does not change the encoding.')}
      {toggle('cvdSafe', 'Colour-vision safe', 'Shape is already load-bearing for type — this raises it further.')}

      <h3>Account</h3>
      <div className="set-row">
        <div>
          <div className="k">Export everything</div>
          <div className="d">Structured JSON — nodes, edges, spans, outcomes. ⭐ A graph you cannot get out of a product is a graph you do not own.</div>
        </div>
        <button className="btn" onClick={exportGraph}>Export</button>
      </div>
      <div className="set-row">
        <div>
          <div className="k danger">Delete everything</div>
          {/* ⚠️ Saying only "delete everything" would be a lie. The structural
              half of the ledger is not personal data and it survives — a
              regulator would care, and so would a student. */}
          <div className="d">
            Your labels and measurements become unrecoverable. The <b>shape</b> of the graph
            and <b>whether your predictions matched</b> survive as anonymous data — that is
            what destroying the key does, and it would be dishonest to imply otherwise.
          </div>
        </div>
        <button className="btn danger" disabled title="Not wired in the demo">Delete</button>
      </div>
    </section>
  );
}
