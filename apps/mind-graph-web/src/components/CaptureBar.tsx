/**
 * The one capture bar. `F01 §3`, re-worked for **F7**.
 *
 * F7's risk: routing has to be right almost every time or it is worse than
 * folders — a misfiled item you cannot find is more frustrating than one you
 * filed yourself, and correcting a misroute is itself the tax we removed.
 *
 * ⭐ The fix is not better guessing. It is making a wrong guess cost ONE
 * keystroke, and making the guess visible so it can be wrong out loud:
 *
 *   1. Never ask up front. Route optimistically and SHOW the decision —
 *      "filed as Note · change". The tax only appears when the guess is wrong.
 *   2. One click to correct, and the correction is recorded. The ledger has a
 *      CORRECTION event type for exactly this; a fix the system does not
 *      learn from is a fix the student pays for twice.
 *   3. ⚠️ Confidence-gated asking. Confident → file silently. Genuinely
 *      unsure → ask AT capture. Guessing wrong silently is worse than asking;
 *      asking every time is worse than both.
 *   4. Prefixes for the fluent: `? ` question, `! ` claim, `> ` artifact.
 *      Costs nothing and lets a heavy user bypass the router entirely.
 *
 * ⚠️ The number to watch is CORRECTION RATE, not routing accuracy. A wrong
 * guess corrected in one click is cheap; a wrong guess never noticed is the
 * failure that actually loses the user.
 */
import { useMemo, useRef, useState } from "react";
import "./CaptureBar.css";

export type CaptureType = "Question" | "Claim" | "Artifact" | "Source" | "Concept" | "Note";

const TYPES: Array<{ t: CaptureType; glyph: string }> = [
  { t: "Concept", glyph: "◆" }, { t: "Question", glyph: "?" },
  { t: "Claim", glyph: "▲" }, { t: "Artifact", glyph: "■" },
  { t: "Source", glyph: "▪" }, { t: "Note", glyph: "·" },
];
const GLYPH = Object.fromEntries(TYPES.map((x) => [x.t, x.glyph])) as Record<CaptureType, string>;

/** Explicit prefixes always win — an explicit user beats any classifier. */
const PREFIX: Record<string, CaptureType> = { "?": "Question", "!": "Claim", ">": "Artifact" };

export interface Routed { type: CaptureType; confidence: number; explicit: boolean; }

/**
 * The local router. Deliberately cheap and legible — Tier 0, no model.
 * ⚠️ It returns a CONFIDENCE, not just a type, because the whole design rests
 * on being able to tell "I know" from "I guessed".
 */
export function route(text: string): Routed {
  const raw = text.trim();
  const p = PREFIX[raw[0]];
  if (p) return { type: p, confidence: 1, explicit: true };

  const t = raw.toLowerCase();
  if (/^https?:\/\//.test(raw) || /\b(doi|arxiv|et al\.?)\b/.test(t))
    return { type: "Source", confidence: 0.95, explicit: false };
  if (raw.endsWith("?") || /^(how|why|what|when|does|do|is|are|can|should)\b/.test(t))
    return { type: "Question", confidence: 0.9, explicit: false };
  // ⚠️ `k?ω|ohm` could not match "kohm": \b fails between k and o, both word
  // characters — and a trailing \b fails after "%" for the same reason. A
  // measurement the router files as a Note is exactly the silent misroute F7
  // is about, so the unit alternation is written out and the tail is a
  // negative lookahead rather than a word boundary.
  if (/\b\d+(\.\d+)?\s*(%|[kmµu]?ohms?|[kmµu]?ω|ms|µs|us|k?hz|m?[av]|db)(?![a-z0-9])/.test(t))
    return { type: "Artifact", confidence: 0.72, explicit: false };
  if (/\.(py|c|h|cpp|ts|tsx|md|csv|pdf|ino)\b/.test(t) || /[/\\]/.test(raw))
    return { type: "Artifact", confidence: 0.8, explicit: false };
  if (/\b(because|therefore|so that|implies|means that|suggests)\b/.test(t))
    return { type: "Claim", confidence: 0.68, explicit: false };
  // ⚠️ Low confidence, and it says so. Note is the honest fallback, not a
  // confident answer dressed as one.
  return { type: "Note", confidence: 0.35, explicit: false };
}

/** Below this the router asks instead of guessing. */
const ASK_BELOW = 0.5;

/**
 * ⚠️ BUG FIX, confirmed live with Playwright: this used to call `setFiled(...)`
 * unconditionally for every type, so the UI said "filed as ■ Artifact" while
 * the network trace showed the actual request was `GET /query` — a false
 * success message. Traced: the backend has no route for "create a bare node
 * of this type" — `propose` requires a structured edge + basis (a subject and
 * a justification a raw capture doesn't have), and `ingest` is document
 * extraction, not single-item capture. That's Sources/Phase 6, already
 * self-disclosed as unbuilt elsewhere in this app.
 *
 * The honest fix is not to fabricate a write path. Only `Question` has a real
 * destination today (ask/search). Everything else is held in a local,
 * honestly-labeled queue — "captured, not filed yet" — instead of claiming a
 * persistence that doesn't exist.
 */
export function CaptureBar({ onSubmit, onCorrect }: {
  /** called ONLY for Question — the one type with a real backend destination */
  onSubmit: (text: string, type: CaptureType, routed: Routed) => void;
  /** fires when the student overrides the router — the learning signal */
  onCorrect?: (text: string, from: CaptureType, to: CaptureType) => void;
}) {
  const [text, setText] = useState("");
  const [asking, setAsking] = useState<string | null>(null);
  const [filed, setFiled] = useState<{ text: string; type: CaptureType; from: CaptureType; persisted: boolean } | null>(null);
  const [picking, setPicking] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const r = useMemo(() => route(text), [text]);
  const body = (s: string) => (PREFIX[s.trim()[0]] ? s.trim().slice(1).trim() : s.trim());

  const commit = (raw: string, type: CaptureType, routed: Routed) => {
    // ⚠️ persisted reflects reality: only Question actually reaches the
    // backend. Everything else is queued, not filed — see the note above.
    const persisted = type === "Question";
    if (persisted) onSubmit(body(raw), type, routed);
    setFiled({ text: body(raw), type, from: routed.type, persisted });
    setText(""); setAsking(null); setPicking(false);
    inputRef.current?.focus();
  };

  const submit = () => {
    const raw = text.trim();
    if (!raw) return;
    const routed = route(raw);
    // confidence-gated: ask only when genuinely unsure
    if (!routed.explicit && routed.confidence < ASK_BELOW) { setAsking(raw); return; }
    commit(raw, routed.type, routed);
  };

  const correct = (to: CaptureType) => {
    if (!filed) return;
    if (to !== filed.type) onCorrect?.(filed.text, filed.type, to);
    setFiled({ ...filed, type: to });
    setPicking(false);
  };

  return (
    <div className="cap">
      <div className="cap-in">
        {/* the live guess, before you even commit — the router is never a
            surprise, which is most of what made routing feel arbitrary */}
        <span className="cap-guess" title={`${r.type} · ${Math.round(r.confidence * 100)}% sure`}>
          {text.trim() ? GLYPH[r.type] : "＋"}
        </span>
        <input
          ref={inputRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); if (e.key === "Escape") { setText(""); setAsking(null); } }}
          placeholder="Capture anything — a note, a question, a measurement, a link"
        />
        <kbd>↵</kbd>
      </div>

      {/* ⚠️ Asked, not guessed. This row appears only below the confidence
          floor — the alternative is filing it wrong silently. */}
      {asking && (
        <div className="cap-ask">
          <span>Not sure where this goes —</span>
          {TYPES.map(({ t, glyph }) => (
            <button key={t} onClick={() => commit(asking, t, route(asking))}>
              <i>{glyph}</i>{t}
            </button>
          ))}
        </div>
      )}

      {/* the decision, shown. One click to change it. ⚠️ the verb changes with
          reality: "filed" only when something actually reached the backend. */}
      {filed && !asking && (
        <div className={"cap-filed" + (filed.persisted ? "" : " cap-pending")}>
          <span className="cap-f-t">
            {filed.persisted ? "filed as" : "captured as"} <b>{GLYPH[filed.type]} {filed.type}</b>
          </span>
          <span className="cap-f-x">{filed.text.slice(0, 52)}{filed.text.length > 52 ? "…" : ""}</span>
          {!filed.persisted && <span className="cap-f-note">not yet saved — filing lands with Sources</span>}
          <button className="cap-change" onClick={() => setPicking((p) => !p)}>
            {picking ? "keep" : "change"}
          </button>
          <button className="cap-dismiss" onClick={() => setFiled(null)} aria-label="dismiss">×</button>
          {picking && (
            <div className="cap-pick">
              {TYPES.map(({ t, glyph }) => (
                <button key={t} className={t === filed.type ? "on" : ""} onClick={() => correct(t)}>
                  <i>{glyph}</i>{t}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="cap-tips">
        <span><b>?</b> question</span><span><b>!</b> claim</span><span><b>&gt;</b> artifact</span>
      </div>
    </div>
  );
}
