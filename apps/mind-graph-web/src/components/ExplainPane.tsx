/**
 * Why do I believe this? — Frontend/01 §4.0a.
 *
 * ⭐ Retracted support is its own block. A claim that LOST its evidence is a
 * different state from one that never had any, and rendering them identically
 * is what makes a system feel like it is hiding something.
 */
import type { Explain } from "../lib/api";

export function ExplainPane({ data, onPick }: { data: Explain; onPick?: (id: string) => void }) {
  const block = (label: string, ids: string[], cls = "") =>
    ids.length ? (
      <section className={`ex-block ${cls}`}>
        <h4>{label}</h4>
        <ul>
          {ids.map((id) => (
            <li key={id}><button onClick={() => onPick?.(id)}>{id}</button></li>
          ))}
        </ul>
      </section>
    ) : null;

  return (
    <div className="explain">
      <header>
        <h3>{data.id}</h3>
        <div className="tags">
          <span className={`tag tag--${data.support}`}>{data.support}</span>
          <span className="tag">{data.strength}</span>
          <span className="tag">corroboration {data.corroboration}</span>
          {/* ⭐ Information, not a warning — the value is the click, which asks
              what a different method would look like. */}
          {data.single_method && <span className="tag tag--rim">◑ one method</span>}
        </div>
      </header>
      {block("← supported by", data.supported_by)}
      {block("⚡ contradicted by", data.contradicted_by, "ex-block--against")}
      {block("✗ support you retracted", data.retracted_support, "ex-block--gone")}
      {data.retracted_support.length > 0 && (
        <p className="note">A claim that lost its evidence is not the same as one that never had any.</p>
      )}
    </div>
  );
}
