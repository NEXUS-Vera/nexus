
export function CalibrationCounter({ predictions, verified }: { predictions: number, verified: number }) {
  // Simple calibration counter, e.g. "4 / 5 corroborated"
  return (
    <div style={{
      fontFamily: 'var(--font-mono)',
      color: 'var(--text-muted)',
      fontSize: 'var(--fs-sm)',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    }}>
      <span>Calibration:</span>
      <strong style={{ color: 'var(--text)' }}>{verified} / {predictions} corroborated</strong>
    </div>
  );
}
