import { useEffect, useState } from 'react';
import { getHealthz, type HealthzResponse } from '../../api/client';

export function ProviderModePill() {
  const [health, setHealth] = useState<HealthzResponse>();
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    getHealthz().then(value => { if (!cancelled) setHealth(value); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, []);
  // Only recognized enums become display text. Never dump configuration or errors.
  const mode = health?.initializationProvider === 'llm' ? 'LIVE' : health?.initializationProvider === 'fixture' ? 'FIXTURE' : 'UNKNOWN';
  return <div style={{ position: 'relative' }} onKeyDown={event => { if (event.key === 'Escape') setOpen(false); }}>
    <button type="button" aria-expanded={open} aria-controls="toolchain-diagnostics" onClick={() => setOpen(value => !value)} style={{ borderRadius: 16, padding: '4px 10px' }}>{mode}</button>
    {open && <div id="toolchain-diagnostics" role="region" aria-label="Toolchain diagnostics" style={{ position: 'absolute', right: 0, top: '100%', width: 280, background: 'var(--nx-surface, white)', color: 'var(--nx-text, #111)', border: '1px solid #888', padding: 12 }}>
      <strong>Toolchain diagnostics</strong>
      <p>{failed ? 'Provider health unavailable.' : `Initialization provider: ${mode}.`}</p>
      <p>Storage: {['sqlite', 'memory', 'postgres'].includes(health?.storageBackend ?? '') ? health?.storageBackend : 'unknown'}</p>
      <p>PlatformIO, simulator and Python availability: not reported by health endpoint. Inspect run logs for tool failures.</p>
      <p>{mode === 'FIXTURE' ? 'Fixture results are regression evidence.' : 'Provider mode does not establish real tool execution.'}</p>
      <button type="button" onClick={() => setOpen(false)}>Close diagnostics</button>
    </div>}
  </div>;
}
