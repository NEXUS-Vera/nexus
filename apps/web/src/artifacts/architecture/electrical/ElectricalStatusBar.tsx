import { themeColors } from '../../../lib/theme';

type Props = {
  isDark: boolean;
  blocking: number;
  warnings: number;
  passed: number;
  onOpenDetails?: () => void;
};

export function ElectricalStatusBar({
  isDark,
  blocking,
  warnings,
  passed,
  onOpenDetails,
}: Props) {
  const t = themeColors(isDark);
  return (
    <button
      type="button"
      data-testid="electrical-status-bar"
      onClick={onOpenDetails}
      style={{
        width: '100%',
        border: 'none',
        borderTop: `1px solid ${t.border}`,
        background: t.surface,
        color: t.textSec,
        textAlign: 'left',
        padding: '8px 16px',
        fontSize: 12,
        cursor: onOpenDetails ? 'pointer' : 'default',
      }}
    >
      <strong style={{ color: blocking > 0 ? '#D14343' : warnings > 0 ? '#DC6B20' : '#159A7A' }}>
        {blocking} blocking
      </strong>
      {' · '}
      {warnings} warnings · {passed} checks passed
    </button>
  );
}
