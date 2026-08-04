import { useMemo } from 'react';
import type { Artifact } from '@nexus/contracts';
import { WorkspaceHeader } from '../../components/layout/WorkspaceHeader';
import { themeColors } from '../../lib/theme';

type Props = {
  artifact: Extract<Artifact, { artifactType: 'functional-architecture' }>;
  changeIndicator?: string;
  isDark: boolean;
  selectedNodeId: string | null;
  onSelectNode: (id: string) => void;
};

const TYPE_COLORS: Record<string, string> = {
  sensing: '#168AAD',
  processing: '#3563E9',
  control: '#7667D9',
  storage: '#64748B',
  communication: '#159A7A',
  power: '#DC6B20',
  output: '#D58A12',
  actuation: '#D14343',
  analysis: '#6C8DFF',
  'user-interface': '#3563E9',
  input: '#168AAD',
  'external-system': '#858B98',
};

export function ArchitectureWorkspace({
  artifact,
  changeIndicator,
  isDark,
  selectedNodeId,
  onSelectNode,
}: Props) {
  const t = themeColors(isDark);
  const { nodes, edges, systemBoundary, architectureMaturity, requirementCoverage, unresolvedDecisions, assumptions } =
    artifact.content;

  const layout = useMemo(() => {
    const cols = Math.max(2, Math.ceil(Math.sqrt(nodes.length)));
    return nodes.map((node, index) => {
      const col = index % cols;
      const row = Math.floor(index / cols);
      return {
        ...node,
        x: 80 + col * 180,
        y: 60 + row * 120,
      };
    });
  }, [nodes]);

  const selected = nodes.find((n) => n.nodeId === selectedNodeId) ?? nodes[0];
  const width = Math.max(640, ...layout.map((n) => n.x + 140));
  const height = Math.max(360, ...layout.map((n) => n.y + 100));

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }} data-testid="workspace-architecture">
      <WorkspaceHeader
        title="Architecture"
        subtitle={`Functional maturity: ${architectureMaturity} · Boundary: ${systemBoundary}`}
        version={artifact.artifactVersion}
        lifecycleStatus={artifact.lifecycleStatus}
        evidenceStatus={artifact.evidenceStatus}
        approvalStatus={artifact.approvalStatus}
        changeIndicator={changeIndicator}
        isDark={isDark}
      />
      <div
        style={{
          padding: '8px 16px',
          borderBottom: `1px solid ${t.border}`,
          background: t.surface,
          display: 'flex',
          gap: 8,
          alignItems: 'center',
        }}
      >
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: t.cobalt,
            background: t.cobaltSelected,
            padding: '4px 10px',
            borderRadius: 6,
          }}
        >
          System
        </span>
        <span
          title="Electrical view is a design placeholder until implementation architecture exists"
          style={{ fontSize: 12, color: t.textMuted, padding: '4px 10px' }}
        >
          Electrical (placeholder)
        </span>
        <span
          title="Physical view is a design placeholder until implementation architecture exists"
          style={{ fontSize: 12, color: t.textMuted, padding: '4px 10px' }}
        >
          Physical (placeholder)
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 12, color: t.textSec }}>
          Coverage: {requirementCoverage.coveredRequirementIds.length} requirements
        </span>
      </div>
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'minmax(0,1.4fr) minmax(260px,0.8fr)', overflow: 'hidden' }}>
        <div style={{ overflow: 'auto', background: t.bg, padding: 12 }}>
          <svg width={width} height={height} role="img" aria-label="Functional architecture canvas">
            {edges.map((edge) => {
              const from = layout.find((n) => n.nodeId === edge.fromNodeId);
              const to = layout.find((n) => n.nodeId === edge.toNodeId);
              if (!from || !to) return null;
              return (
                <g key={edge.edgeId}>
                  <line
                    x1={from.x + 60}
                    y1={from.y + 28}
                    x2={to.x + 60}
                    y2={to.y + 28}
                    stroke={t.border}
                    strokeWidth={2}
                  />
                  <title>{`${edge.flowType}: ${edge.description}`}</title>
                </g>
              );
            })}
            {layout.map((node) => {
              const active = selected?.nodeId === node.nodeId;
              return (
                <g
                  key={node.nodeId}
                  transform={`translate(${node.x}, ${node.y})`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => onSelectNode(node.nodeId)}
                >
                  <rect
                    width={120}
                    height={56}
                    rx={8}
                    fill={active ? t.cobaltSelected : t.surface}
                    stroke={active ? t.cobalt : t.border}
                    strokeWidth={active ? 2 : 1}
                  />
                  <circle cx={14} cy={28} r={5} fill={TYPE_COLORS[node.functionalType] ?? t.cobalt} />
                  <text x={26} y={24} fontSize={11} fontWeight={600} fill={t.text}>
                    {node.name.length > 14 ? `${node.name.slice(0, 14)}…` : node.name}
                  </text>
                  <text x={26} y={40} fontSize={10} fill={t.textMuted}>
                    {node.functionalType}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
        <aside style={{ borderLeft: `1px solid ${t.border}`, overflow: 'auto', padding: 16, background: t.surface }}>
          {selected ? (
            <div style={{ display: 'grid', gap: 10 }}>
              <h3 style={{ margin: 0, color: t.text }}>{selected.name}</h3>
              <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>{selected.functionalType}</p>
              <h4 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Responsibilities</h4>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: t.text }}>
                {selected.responsibilities.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <h4 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Requirement coverage</h4>
              <p style={{ margin: 0, fontSize: 12, color: t.text }}>
                {selected.satisfiesRequirementIds.join(', ')}
              </p>
            </div>
          ) : null}
          {unresolvedDecisions.length ? (
            <div style={{ marginTop: 16 }}>
              <h4 style={{ margin: '0 0 6px', fontSize: 12, color: t.textMuted }}>Unresolved decisions</h4>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
                {unresolvedDecisions.map((item) => (
                  <li key={item.questionId}>{item.displayId ?? item.questionId}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {assumptions.length ? (
            <div style={{ marginTop: 16 }}>
              <h4 style={{ margin: '0 0 6px', fontSize: 12, color: t.textMuted }}>Assumptions</h4>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
                {assumptions.map((item) => (
                  <li key={item.assumptionId}>{item.statement}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div style={{ marginTop: 16 }}>
            <h4 style={{ margin: '0 0 6px', fontSize: 12, color: t.textMuted }}>Flows</h4>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
              {edges.map((edge) => {
                const from = nodes.find((n) => n.nodeId === edge.fromNodeId)?.name ?? edge.fromNodeId;
                const to = nodes.find((n) => n.nodeId === edge.toNodeId)?.name ?? edge.toNodeId;
                return (
                  <li key={edge.edgeId}>
                    {from} → {to} ({edge.flowType})
                  </li>
                );
              })}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
