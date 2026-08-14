/**
 * A disagreement, as two columns.
 *
 * ⭐ Never a verdict. The system holds literature, belief and bench, and its
 * job is to put two of them side by side — the student picking a winner is the
 * entire pedagogical point.
 */
export interface TensionCardProps {
  level: string;
  kind: string;
  a: string;
  b: string;
  framing: string;
  onResolve?: (choice: string) => void;
}

/** Actions differ by kind, because the useful next step does. */
const ACTIONS: Record<string, string[]> = {
  BOUNDARY: ["Narrow the claim", "They're comparable", "My setup is wrong"],
  CONFLICT: ["What changed between them?", "Re-run one"],
  SELF: ["Supersede the older", "Both, different regimes"],
  CHECK: ["Check the setup", "Trust the measurement"],
  FINDING: ["Escalate — this may be real", "Look for a third method"],
  LITERATURE: ["Which applies to me?", "Neither, in my regime"],
};

export function TensionCard({ level, kind, a, b, framing, onResolve }: TensionCardProps) {
  return (
    <article className={`tension tension--${level}`}>
      <header>
        <span className="lvl">{level}</span>
        <span className="kind">{kind}</span>
      </header>
      <div className="cols">
        <div className="col"><span className="src">{a}</span></div>
        <div className="x">⚡</div>
        <div className="col"><span className="src">{b}</span></div>
      </div>
      <p className="framing">{framing}</p>
      <footer>
        {(ACTIONS[kind] ?? ACTIONS.CHECK).map((t, i) => (
          <button key={t} className={i === 0 ? "pri" : ""} onClick={() => onResolve?.(t)}>{t}</button>
        ))}
        {/* ⚠️ Dismissals lower priority; they never delete. It comes back when
            new evidence lands. */}
        <button className="ghost" onClick={() => onResolve?.("dismiss")}>Not now</button>
      </footer>
    </article>
  );
}
