import type { CSSProperties, ReactNode } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { themeColors } from '../../../../lib/theme';
import type { ElectricalNodeData } from '../registry/node-renderers';
import type { ElectricalVisualInterface, ElectricalVisualStatus } from '../types';

function statusTone(status: ElectricalVisualStatus, isDark: boolean): string {
  if (status === 'blocking') return '#D14343';
  if (status === 'at-risk' || status === 'provisional') return '#DC6B20';
  if (status === 'simulation-surrogate') return '#B7791F';
  if (status === 'simulation-supported') return '#159A7A';
  if (status === 'unsupported-simulation') return '#858B98';
  return themeColors(isDark).border;
}

function statusLabel(status: ElectricalVisualStatus): string | null {
  if (status === 'provisional') return 'Provisional';
  if (status === 'unverified') return 'Unverified';
  if (status === 'at-risk') return 'At risk';
  if (status === 'blocking') return 'Blocking';
  if (status === 'simulation-surrogate') return 'Surrogate-ready';
  if (status === 'simulation-supported') return 'Sim-ready';
  if (status === 'unsupported-simulation') return 'Sim unsupported';
  return null;
}

function visibleInterfaces(interfaces: ElectricalVisualInterface[]): ElectricalVisualInterface[] {
  const active = interfaces.filter((iface) => iface.active);
  if (active.length > 0) return active.slice(0, 8);
  return interfaces.slice(0, 6);
}

export function ElectricalNodeShell({
  data,
  accent,
  icon,
  children,
}: NodeProps<Node<ElectricalNodeData>> & {
  accent: string;
  icon: string;
  children?: ReactNode;
}) {
  const t = themeColors(data.isDark);
  const visual = data.visual;
  const selected = data.selected;
  const tone = statusTone(visual.status, data.isDark);
  const badge = statusLabel(visual.status);
  const interfaces = visibleInterfaces(visual.interfaces);
  const left = interfaces.filter((iface) => iface.side === 'left');
  const right = interfaces.filter((iface) => iface.side === 'right');

  const style: CSSProperties = {
    minWidth: 188,
    maxWidth: 240,
    borderRadius: 10,
    border: `1.5px solid ${selected ? t.cobalt : tone}`,
    background: selected ? t.cobaltSelected : t.surface,
    boxShadow: selected ? `0 0 0 1px ${t.cobalt}` : `0 1px 2px rgba(16,24,40,0.06)`,
    color: t.text,
    fontSize: 12,
    overflow: 'hidden',
  };

  return (
    <div
      style={style}
      data-testid={`electrical-node-${visual.id}`}
      aria-label={`${visual.title}, ${visual.subtitle}`}
    >
      <div
        style={{
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          padding: '8px 10px',
          borderBottom: `1px solid ${t.border}`,
          background: data.isDark ? '#182131' : '#F8FAFC',
        }}
      >
        <div
          aria-hidden
          style={{
            width: 22,
            height: 22,
            borderRadius: 6,
            background: accent,
            color: '#fff',
            display: 'grid',
            placeItems: 'center',
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          {icon}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontWeight: 650, lineHeight: 1.25 }}>{visual.title}</div>
          <div style={{ color: t.textMuted, fontSize: 10, marginTop: 2 }}>{visual.subtitle}</div>
        </div>
        {badge ? (
          <span
            style={{
              fontSize: 9,
              fontWeight: 600,
              color: tone,
              border: `1px solid ${tone}`,
              borderRadius: 999,
              padding: '2px 6px',
              whiteSpace: 'nowrap',
            }}
          >
            {badge}
          </span>
        ) : null}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, padding: '8px 6px' }}>
        <div>
          {left.map((iface, index) => (
            <div
              key={iface.interfaceId}
              style={{
                position: 'relative',
                padding: '3px 8px 3px 12px',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                fontSize: 10,
                color: t.textSec,
              }}
            >
              <Handle
                id={iface.interfaceId}
                type="target"
                position={Position.Left}
                style={{ left: -2, background: accent, width: 8, height: 8 }}
              />
              {iface.label}
              {index === left.length - 1 && right.length === 0 ? (
                <Handle
                  type="source"
                  position={Position.Right}
                  style={{ opacity: 0, pointerEvents: 'none' }}
                />
              ) : null}
            </div>
          ))}
          {left.length === 0 ? (
            <Handle type="target" position={Position.Left} style={{ background: accent }} />
          ) : null}
        </div>
        <div>
          {right.map((iface) => (
            <div
              key={iface.interfaceId}
              style={{
                position: 'relative',
                padding: '3px 12px 3px 8px',
                textAlign: 'right',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                fontSize: 10,
                color: t.textSec,
              }}
            >
              {iface.label}
              <Handle
                id={iface.interfaceId}
                type="source"
                position={Position.Right}
                style={{ right: -2, background: accent, width: 8, height: 8 }}
              />
            </div>
          ))}
          {right.length === 0 ? (
            <Handle type="source" position={Position.Right} style={{ background: accent }} />
          ) : null}
        </div>
      </div>
      {children}
    </div>
  );
}
