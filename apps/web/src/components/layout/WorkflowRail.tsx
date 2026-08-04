import {
  Activity,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Database,
  Settings,
  Zap,
} from 'lucide-react';
import type { Artifact } from '@nexus/contracts';
import {
  ARTIFACT_REGISTRY,
  WORKFLOW_GROUPS,
  type ArtifactDefinition,
} from '../../artifacts/registry';
import type { ArtifactRouteKey } from '../../artifacts/types';
import { LIFECYCLE_DOT, themeColors } from '../../lib/theme';
import { selectArtifactByType } from '../../artifacts';

type WorkflowRailProps = {
  selectedArtifact: ArtifactRouteKey;
  onSelectArtifact: (key: ArtifactRouteKey) => void;
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  isDark: boolean;
  artifacts: Artifact[];
  nextAction?: Extract<Artifact, { artifactType: 'next-action' }>;
  onOpenNextAction: () => void;
  onOpenHistory: () => void;
  changeByType?: Record<string, string>;
};

function StatusDot({ status, label }: { status: string; label: string }) {
  const color = LIFECYCLE_DOT[status] ?? LIFECYCLE_DOT.unavailable;
  return (
    <span
      title={`${label}: ${status}`}
      aria-hidden
      style={{
        width: 7,
        height: 7,
        borderRadius: '50%',
        background: color,
        display: 'inline-block',
        flexShrink: 0,
      }}
    />
  );
}

function railStatusFor(
  def: ArtifactDefinition,
  artifacts: Artifact[],
  changeByType?: Record<string, string>,
): { status: string; version?: number } {
  if (def.availability === 'placeholder' || !def.artifactType) {
    return { status: 'unavailable' };
  }
  const live = selectArtifactByType(artifacts, def.artifactType);
  if (!live) {
    return {
      status: def.availability === 'proof' ? 'drafted' : 'unavailable',
    };
  }
  const change = changeByType?.[def.artifactType];
  if (change === 'Affected') return { status: 'affected', version: live.artifactVersion };
  if (change === 'Stale') return { status: 'stale', version: live.artifactVersion };
  return { status: live.lifecycleStatus, version: live.artifactVersion };
}

export function WorkflowRail({
  selectedArtifact,
  onSelectArtifact,
  collapsed,
  onCollapsedChange,
  isDark,
  artifacts,
  nextAction,
  onOpenNextAction,
  onOpenHistory,
  changeByType,
}: WorkflowRailProps) {
  const t = themeColors(isDark);
  const next = nextAction?.content;

  if (collapsed) {
    return (
      <nav
        aria-label="Workflow artifacts"
        style={{
          width: '100%',
          height: '100%',
          borderRight: `1px solid ${t.border}`,
          background: t.surface,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '8px 0',
          gap: 2,
          overflowY: 'auto',
        }}
      >
        <button
          type="button"
          onClick={() => onCollapsedChange(false)}
          aria-label="Expand workflow rail"
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            border: `1px solid ${t.border}`,
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: t.textSec,
            marginBottom: 8,
          }}
        >
          <ChevronRight size={15} aria-hidden />
        </button>
        {WORKFLOW_GROUPS.flatMap((group) =>
          group.artifacts.map((key) => {
            const item = ARTIFACT_REGISTRY[key];
            const Icon = item.icon;
            const selected = selectedArtifact === key;
            const { status } = railStatusFor(item, artifacts, changeByType);
            return (
              <button
                key={key}
                type="button"
                title={item.label}
                aria-label={item.label}
                aria-current={selected ? 'page' : undefined}
                onClick={() => onSelectArtifact(key)}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  border: selected ? `1px solid ${t.cobalt}22` : 'none',
                  background: selected ? t.cobaltSelected : 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: selected ? t.cobalt : t.textSec,
                  position: 'relative',
                }}
              >
                <Icon size={16} aria-hidden />
                <span
                  style={{
                    position: 'absolute',
                    top: 4,
                    right: 4,
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: LIFECYCLE_DOT[status] ?? LIFECYCLE_DOT.unavailable,
                  }}
                />
              </button>
            );
          }),
        )}
      </nav>
    );
  }

  return (
    <nav
      aria-label="Workflow artifacts"
      style={{
        height: '100%',
        borderRight: `1px solid ${t.border}`,
        background: t.surface,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {next ? (
        <button
          type="button"
          onClick={onOpenNextAction}
          style={{
            margin: 10,
            padding: '10px 12px',
            background: t.cobaltTint,
            border: `1px solid ${t.cobalt}33`,
            borderRadius: 8,
            borderLeft: `3px solid ${t.cobalt}`,
            textAlign: 'left',
            cursor: 'pointer',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Zap size={12} color={t.cobalt} aria-hidden />
            <span style={{ fontSize: 11, fontWeight: 600, color: t.cobalt }}>Next Action</span>
            {nextAction ? (
              <span style={{ marginLeft: 'auto', fontSize: 10, color: t.textMuted }}>
                v{nextAction.artifactVersion}
              </span>
            ) : null}
          </div>
          <div style={{ fontSize: 12, fontWeight: 600, color: t.text, marginBottom: 2 }}>
            {next.title}
          </div>
          <div style={{ fontSize: 11, color: t.textSec, marginBottom: 6 }}>{next.description}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: 10,
                color: t.textMuted,
                background: t.surface3,
                padding: '2px 6px',
                borderRadius: 3,
                border: `1px solid ${t.border}`,
              }}
            >
              {next.priority} · {next.owner}
            </span>
            {next.blocks.length > 0 ? (
              <span
                style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, color: '#DC6B20' }}
              >
                <AlertTriangle size={10} aria-hidden />
                {next.blocks.length} blocker{next.blocks.length === 1 ? '' : 's'}
              </span>
            ) : null}
          </div>
        </button>
      ) : null}

      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
        {WORKFLOW_GROUPS.map((group) => (
          <div key={group.label} style={{ marginBottom: 4 }}>
            <div
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: t.textMuted,
                letterSpacing: '0.08em',
                padding: '8px 8px 4px',
              }}
            >
              {group.label}
            </div>
            {group.artifacts.map((key) => {
              const item = ARTIFACT_REGISTRY[key];
              const Icon = item.icon;
              const selected = selectedArtifact === key;
              const { status, version } = railStatusFor(item, artifacts, changeByType);
              return (
                <button
                  key={key}
                  type="button"
                  aria-label={item.label}
                  aria-current={selected ? 'page' : undefined}
                  onClick={() => onSelectArtifact(key)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '7px 8px',
                    borderRadius: 6,
                    border: 'none',
                    cursor: 'pointer',
                    background: selected ? t.cobaltSelected : 'transparent',
                    color: selected ? t.cobalt : t.text,
                    fontSize: 13,
                    fontWeight: selected ? 600 : 400,
                    textAlign: 'left',
                    marginBottom: 1,
                    boxShadow: selected ? `inset 3px 0 0 ${t.cobalt}` : 'none',
                  }}
                >
                  <Icon size={15} strokeWidth={selected ? 2.2 : 1.8} aria-hidden />
                  <span style={{ flex: 1 }} aria-hidden>
                    {item.label}
                  </span>
                  {version != null ? (
                    <span style={{ fontSize: 10, color: t.textMuted }} aria-hidden>
                      v{version}
                    </span>
                  ) : (
                    <span style={{ fontSize: 10, color: t.textMuted }} aria-hidden>
                      Soon
                    </span>
                  )}
                  <StatusDot status={status} label={item.label} />
                </button>
              );
            })}
          </div>
        ))}
      </div>

      <div style={{ borderTop: `1px solid ${t.border}`, padding: 8 }}>
        <button
          type="button"
          onClick={onOpenHistory}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '7px 8px',
            borderRadius: 6,
            border: 'none',
            cursor: 'pointer',
            background: 'transparent',
            color: t.textSec,
            fontSize: 12,
            textAlign: 'left',
          }}
        >
          <Activity size={14} aria-hidden />
          Project Activity
        </button>
        <div
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '7px 8px',
            color: t.textMuted,
            fontSize: 12,
          }}
          title="Evidence explorer is not available yet"
        >
          <Database size={14} aria-hidden />
          Evidence Explorer
          <span style={{ marginLeft: 'auto', fontSize: 10 }}>Soon</span>
        </div>
        <div
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '7px 8px',
            color: t.textMuted,
            fontSize: 12,
          }}
          title="Settings are not available yet"
        >
          <Settings size={14} aria-hidden />
          Settings
          <span style={{ marginLeft: 'auto', fontSize: 10 }}>Soon</span>
        </div>
      </div>

      <div style={{ borderTop: `1px solid ${t.border}`, padding: '6px 8px' }}>
        <button
          type="button"
          onClick={() => onCollapsedChange(true)}
          aria-label="Collapse workflow rail"
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '6px 8px',
            borderRadius: 6,
            border: 'none',
            cursor: 'pointer',
            background: 'transparent',
            color: t.textMuted,
            fontSize: 11,
          }}
        >
          <ChevronLeft size={13} aria-hidden />
          Collapse
        </button>
      </div>
    </nav>
  );
}
