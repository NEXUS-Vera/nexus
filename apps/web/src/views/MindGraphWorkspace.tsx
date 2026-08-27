import type { ProjectCurrentState } from '@nexus/contracts';
import { ARTIFACT_ORDER, ARTIFACT_REGISTRY } from '../artifacts/registry';
import { selectArtifactByType } from '../artifacts';
import type { ArtifactRouteKey } from '../artifacts/types';
import { themeColors } from '../lib/theme';

type Props = {
  state: ProjectCurrentState;
  isDark: boolean;
  onNavigate: (key: ArtifactRouteKey) => void;
};

export function MindGraphWorkspace({ state, isDark, onNavigate }: Props) {
  const t = themeColors(isDark);
  const nodes = ARTIFACT_ORDER.map((key, index) => {
    const def = ARTIFACT_REGISTRY[key];
    const live =
      def.artifactType == null
        ? undefined
        : selectArtifactByType(
            state.artifacts,
            def.artifactType as any,
          );
    const angle = (index / ARTIFACT_ORDER.length) * Math.PI * 2 - Math.PI / 2;
    return {
      key,
      label: def.shortLabel,
      live: Boolean(live),
      x: 280 + Math.cos(angle) * 160,
      y: 220 + Math.sin(angle) * 140,
    };
  });

  const edges: Array<[ArtifactRouteKey, ArtifactRouteKey]> = [
    ['project-brief', 'requirement-set'],
    ['requirement-set', 'functional-architecture'],
    ['functional-architecture', 'component-plan'],
    ['component-plan', 'firmware'],
    ['firmware', 'analysis'],
    ['analysis', 'test-plan'],
    ['requirement-set', 'test-plan'],
    ['functional-architecture', 'risk-register'],
    ['test-plan', 'risk-register'],
  ];

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 20, background: t.bg }} data-testid="mind-graph">
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <div
          style={{
            marginBottom: 12,
            padding: 12,
            borderRadius: 8,
            border: `1px dashed ${t.border}`,
            background: t.surface,
          }}
        >
          <strong style={{ color: t.text, fontSize: 13 }}>Mind Graph preview</strong>
          <p style={{ margin: '6px 0 0', fontSize: 12, color: t.textSec }}>
            Canonical graph memory is not implemented. This preview derives a minimal dependency graph
            from board artifact slots and live availability — not hardcoded demo component or test nodes.
          </p>
        </div>
        <svg width={560} height={440} role="img" aria-label="Mind graph preview">
          {edges.map(([fromKey, toKey]) => {
            const from = nodes.find((n) => n.key === fromKey);
            const to = nodes.find((n) => n.key === toKey);
            if (!from || !to) return null;
            return (
              <line
                key={`${fromKey}-${toKey}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={t.border}
                strokeWidth={2}
              />
            );
          })}
          {nodes.map((node) => (
            <g
              key={node.key}
              transform={`translate(${node.x}, ${node.y})`}
              style={{ cursor: 'pointer' }}
              onClick={() => onNavigate(node.key)}
            >
              <circle
                r={28}
                fill={node.live ? t.cobaltSelected : t.surface3}
                stroke={node.live ? t.cobalt : t.border}
                strokeWidth={2}
              />
              <text textAnchor="middle" y={4} fontSize={10} fill={t.text} fontWeight={600}>
                {node.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}
