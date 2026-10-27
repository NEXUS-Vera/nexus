import { ProviderModePill } from './provider-mode-pill';
import { Link } from 'react-router-dom';
import { ChevronRight, History, Moon, Search, Sun } from 'lucide-react';
import type { GlobalView } from '../../artifacts/types';
import { themeColors } from '../../lib/theme';

type AppHeaderProps = {
  projectTitle: string;
  projectDomain: string;
  projectId?: string;
  stateVersion: number;
  globalView: GlobalView;
  onGlobalViewChange: (view: GlobalView) => void;
  isDark: boolean;
  onToggleDark: () => void;
  onOpenCommandPalette: () => void;
  onToggleHistory: () => void;
  historyOpen: boolean;
};

const VIEWS: { key: GlobalView; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'workspace', label: 'Workspace' },
  { key: 'mind-graph', label: 'Mind Graph' },
];

function NexusLogo() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden>
      <rect x="2" y="2" width="10" height="10" rx="2.5" fill="#3563E9" />
      <rect x="16" y="2" width="10" height="10" rx="2.5" fill="#3563E9" opacity="0.6" />
      <rect x="2" y="16" width="10" height="10" rx="2.5" fill="#3563E9" opacity="0.6" />
      <rect x="16" y="16" width="10" height="10" rx="2.5" fill="#B8E24A" />
    </svg>
  );
}

export function AppHeader({
  projectTitle,
  projectDomain,
  projectId,
  stateVersion,
  globalView,
  onGlobalViewChange,
  isDark,
  onToggleDark,
  onOpenCommandPalette,
  onToggleHistory,
  historyOpen,
}: AppHeaderProps) {
  const t = themeColors(isDark);

  return (
    <header
      style={{
        height: 64,
        borderBottom: `1px solid ${t.border}`,
        background: t.surface,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: 12,
        flexShrink: 0,
        zIndex: 100,
        fontFamily: 'var(--nx-font)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: '0 0 auto', minWidth: 0 }}>
        <Link to="/" aria-label="New project" style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
          <NexusLogo />
          <span style={{ fontWeight: 700, fontSize: 16, color: t.text }}>Nexus</span>
        </Link>
        <span style={{ width: 1, height: 20, background: t.border }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, minWidth: 0 }}>
          <span style={{ fontSize: 12, color: t.textSec, whiteSpace: 'nowrap' }}>{projectDomain}</span>
          <ChevronRight size={12} color={t.textSec} aria-hidden />
          <span
            style={{
              fontSize: 12,
              color: t.text,
              fontWeight: 500,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              maxWidth: 280,
            }}
            title={projectTitle}
          >
            {projectTitle}
          </span>
          <span style={{ fontSize: 11, color: t.textMuted, marginLeft: 6 }}>v{stateVersion}</span>
          {projectId ? (
            <span style={{ fontSize: 11, color: t.textMuted, marginLeft: 6 }}>{projectId}</span>
          ) : null}
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        <div
          role="tablist"
          aria-label="Global views"
          style={{
            display: 'flex',
            background: t.surface2,
            borderRadius: 8,
            padding: 3,
            gap: 2,
          }}
        >
          {VIEWS.map((view) => {
            const selected = globalView === view.key;
            return (
              <button
                key={view.key}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => onGlobalViewChange(view.key)}
                style={{
                  padding: '5px 14px',
                  borderRadius: 6,
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: selected ? 600 : 400,
                  background: selected ? t.surface : 'transparent',
                  color: selected ? t.cobalt : t.textSec,
                  boxShadow: selected ? '0 1px 3px rgba(0,0,0,0.12)' : 'none',
                }}
              >
                {view.label}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: '0 0 auto' }}>
        <ProviderModePill />
        <button
          type="button"
          onClick={onOpenCommandPalette}
          aria-label="Open command palette"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '5px 10px',
            borderRadius: 6,
            border: `1px solid ${t.border}`,
            background: t.surface3,
            cursor: 'pointer',
            color: t.textSec,
            fontSize: 12,
          }}
        >
          <Search size={13} aria-hidden />
          <span>Search</span>
          <kbd
            style={{
              padding: '1px 5px',
              background: t.surface2,
              borderRadius: 3,
              fontSize: 10,
              fontWeight: 600,
              border: `1px solid ${t.border}`,
            }}
          >
            ⌘K
          </kbd>
        </button>

        <button
          type="button"
          onClick={onToggleHistory}
          aria-pressed={historyOpen}
          aria-label={historyOpen ? 'Hide project history' : 'Show project history'}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '5px 10px',
            borderRadius: 6,
            border: `1px solid ${t.border}`,
            background: historyOpen ? t.cobaltSelected : t.surface3,
            cursor: 'pointer',
            color: historyOpen ? t.cobalt : t.text,
            fontSize: 12,
            fontWeight: 500,
          }}
        >
          <History size={13} aria-hidden />
          History
        </button>

        <button
          type="button"
          onClick={onToggleDark}
          aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 32,
            height: 32,
            borderRadius: 6,
            border: `1px solid ${t.border}`,
            background: 'transparent',
            cursor: 'pointer',
            color: t.textSec,
          }}
        >
          {isDark ? <Sun size={15} aria-hidden /> : <Moon size={15} aria-hidden />}
        </button>
      </div>
    </header>
  );
}
