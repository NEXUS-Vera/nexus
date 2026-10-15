import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type Edge, type EdgeProps } from '@xyflow/react';
import { themeColors } from '../../../../lib/theme';

export type ElectricalEdgeData = {
  label: string;
  emphasis: 'signal' | 'power' | 'bus' | 'unresolved' | 'warning';
  isDark: boolean;
};

function strokeFor(emphasis: ElectricalEdgeData['emphasis'], isDark: boolean): string {
  const t = themeColors(isDark);
  if (emphasis === 'power') return '#DC6B20';
  if (emphasis === 'bus') return t.cobalt;
  if (emphasis === 'warning') return '#D14343';
  if (emphasis === 'unresolved') return t.textMuted;
  return t.border;
}

export function ElectricalEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
}: EdgeProps<Edge<ElectricalEdgeData>>) {
  const emphasis = data?.emphasis ?? 'signal';
  const isDark = data?.isDark ?? false;
  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });
  const stroke = strokeFor(emphasis, isDark);
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke,
          strokeWidth: selected ? 2.5 : emphasis === 'power' ? 2.25 : 1.75,
          strokeDasharray: emphasis === 'unresolved' ? '5 4' : undefined,
        }}
      />
      {data?.label ? (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: 'all',
              fontSize: 10,
              fontWeight: 650,
              color: stroke,
              background: themeColors(isDark).surface,
              border: `1px solid ${stroke}`,
              borderRadius: 999,
              padding: '1px 6px',
            }}
            className="nodrag nopan"
          >
            {data.label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}
