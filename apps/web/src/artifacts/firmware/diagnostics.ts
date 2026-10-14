export type CompilerDiagnostic = {
  path: string;
  line: number;
  column: number;
  severity: 'error' | 'warning';
  message: string;
};

const DIAGNOSTIC_RE =
  /^([^:\s]+):(\d+):(\d+):\s*(error|warning):\s*(.+)$/;

/** Lightweight GCC/PlatformIO diagnostic extraction (raw logs remain authoritative). */
export function parseCompilerDiagnostics(text: string): CompilerDiagnostic[] {
  const out: CompilerDiagnostic[] = [];
  for (const line of text.split('\n')) {
    const match = DIAGNOSTIC_RE.exec(line.trim());
    if (!match) continue;
    out.push({
      path: match[1],
      line: Number(match[2]),
      column: Number(match[3]),
      severity: match[4] as 'error' | 'warning',
      message: match[5],
    });
  }
  return out;
}
