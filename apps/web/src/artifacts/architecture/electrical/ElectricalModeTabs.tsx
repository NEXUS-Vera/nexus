import { themeColors } from '../../../lib/theme';
import type { ElectricalWorkspaceMode } from './types';

type Props = {
  mode: ElectricalWorkspaceMode;
  isDark: boolean;
  onChange: (mode: ElectricalWorkspaceMode) => void;
};

export function ElectricalModeTabs({ mode, isDark, onChange }: Props) {
  const t = themeColors(isDark);
  const tab = (id: ElectricalWorkspaceMode, label: string) => {
    const active = mode === id;
    return (
      <button
        type="button"
        data-testid={`electrical-mode-${id}`}
        aria-pressed={active}
        onClick={() => onChange(id)}
        style={{
          border: `1px solid ${active ? t.cobalt : t.border}`,
          background: active ? t.cobaltSelected : t.surface,
          color: active ? t.cobalt : t.text,
          borderRadius: 7,
          padding: '5px 10px',
          fontSize: 12,
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        {label}
      </button>
    );
  };

  return (
    <div
      role="tablist"
      aria-label="Electrical workspace mode"
      style={{ display: 'flex', gap: 6, alignItems: 'center' }}
    >
      {tab('design', 'Design')}
      {tab('simulation', 'Simulation')}
    </div>
  );
}
