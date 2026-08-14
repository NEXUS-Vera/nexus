/**
 * Share export — Markdown, and print-to-PDF.
 *
 * ⭐ The format is deliberately the one a reader already knows: a title, a
 * one-line answer, a results TABLE, then provenance. That is how a lab report,
 * a preprint and a technical memo are all laid out, so nobody has to learn our
 * document to read it. Inventing a house format here would make the artifact
 * look bespoke, and "bespoke" is the opposite of "verifiable".
 *
 * ⚠️ Failures are not removable from the export either. A Share page that can
 * be cleaned up on the way out is a press release with extra steps, and the
 * whole claim of this document is that it is not one. The export carries the
 * hash for the same reason — a Markdown file someone can edit is a claim, and
 * the hash is what lets a reader go and check.
 *
 * No PDF library. `window.print()` with a print stylesheet produces a correct,
 * selectable, accessible PDF through the browser's own engine — and adds
 * roughly 300 kB less to the bundle than any library that would do it worse.
 */
import type { Artifact, Calibration, Log } from "./api";

const verdict = (a: Artifact) =>
  a.agreement === "matched" ? "matched"
    : a.agreement === "diverged" ? "**diverged**"
    : a.agreement === "inconclusive" ? "inconclusive" : "not run";

const fmtPred = (a: Artifact) =>
  a.predicted ? `${a.predicted.low}–${a.predicted.high} ${a.predicted.unit}` : "—";
const fmtMeas = (a: Artifact) =>
  a.measured?.value != null ? `${a.measured.value} ${a.measured.unit}` : "not run";

export function shareMarkdown(opts: {
  title: string; log: Log; calibration?: Calibration | null;
  stats?: { established: number; contested: number; nodes: number } | null;
}): string {
  const { title, log, calibration, stats } = opts;
  const arts = log.artifacts.filter((a) => a.predicted || a.measured);
  const L: string[] = [];

  L.push(`# ${title}`, "");
  if (stats) {
    L.push(`*${stats.established} established · ${stats.contested} contested · ${stats.nodes} nodes*`, "");
  }

  L.push("## What was proven", "");
  if (arts.length === 0) {
    // ⚠️ Says what would fill it. An export that silently omits an empty
    // section reads as though the section never existed.
    L.push("_No prediction has been measured yet._", "");
  } else {
    L.push("| Artifact | Predicted | Measured | Verdict |",
           "| --- | --- | --- | --- |");
    for (const a of arts) {
      L.push(`| ${a.label ?? a.id} | ${fmtPred(a)} | ${fmtMeas(a)} | ${verdict(a)} |`);
    }
    L.push("");
  }
  if (calibration && calibration.resolved > 0) {
    const pct = calibration.hit_rate != null
      ? ` (${Math.round(calibration.hit_rate * 100)}%)` : "";
    L.push(`**${calibration.matched} of ${calibration.resolved} resolved predictions matched**${pct}.`, "");
  }

  L.push("## How it got there", "");
  for (const e of log.entries) {
    const when = (e.ts || "").slice(0, 10);
    const what = e.labels.length ? e.labels.join(" · ") : `${e.ids.length} item(s)`;
    // ⭐ withdrawals are struck AND tagged — a reader skimming the table sees
    // the strike; a reader grepping the file finds the word.
    L.push(e.retracted ? `- ${when} — ~~${what}~~ *(withdrawn)*`
      : e.type === "dead_end" ? `- ${when} — ${what} *(dead end)*`
      : `- ${when} — ${what}`);
  }
  L.push("");

  L.push("---", "");
  L.push(log.head.verified
    ? "*Ledger chain verifies. Every entry above was written when it says it was.*"
    : "*⚠ This chain does not verify. Treat the order above as unproven.*");
  L.push("", `\`head seq ${log.head.seq}\``, "", `\`${log.head.hash}\``, "");
  L.push(`*Exported ${new Date().toISOString().slice(0, 10)} from Nexus.*`);
  return L.join("\n");
}

export function download(name: string, text: string, mime = "text/markdown") {
  const url = URL.createObjectURL(new Blob([text], { type: `${mime};charset=utf-8` }));
  const a = document.createElement("a");
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  // ⚠️ revoke on the next tick, not immediately — Safari cancels the download
  // if the object URL dies in the same frame as the click.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** Copy for the case where the reader wants it in an email, not a file. */
export async function copyText(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}
