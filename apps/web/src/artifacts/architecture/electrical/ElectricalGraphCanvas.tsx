import { useCallback, useEffect, useMemo, type CSSProperties, type MouseEvent } from 'react';
import {
  Background,
  ConnectionMode,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type OnNodeDrag,
  type Viewport,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { themeColors } from '../../../lib/theme';
import type { GraphLayoutPositions } from '../../../lib/engineering-graph/types';
import { electricalNodeTypes, flowTypeForCategory } from './registry/node-renderers';
import { ElectricalEdge } from './renderers/ElectricalEdge';
import type {
  ElectricalPowerRailVisual,
  ElectricalVisualEdge,
  ElectricalVisualNode,
} from './types';

export type ElectricalGraphCanvasProps = {
  nodes: ElectricalVisualNode[];
  edges: ElectricalVisualEdge[];
  powerRails?: ElectricalPowerRailVisual[];
  isDark: boolean;
  selectedNodeId?: string | null;
  onSelectNode?: (id: string | null) => void;
  onNodeDragStop?: (positions: GraphLayoutPositions, nodeId: string) => void;
  onViewportChange?: (viewport: Viewport) => void;
  fitView?: boolean;
  testId?: string;
};

const edgeTypes = { electrical: ElectricalEdge };

function toFlowNodes(
  dtos: ElectricalVisualNode[],
  selectedNodeId: string | null | undefined,
  isDark: boolean,
): Node[] {
  return dtos.map((node) => ({
    id: node.id,
    type: flowTypeForCategory(node.category),
    position: node.position ?? { x: 0, y: 0 },
    data: {
      visual: node,
      selected: selectedNodeId === node.id,
      isDark,
    },
    selected: selectedNodeId === node.id,
  }));
}

function toFlowEdges(dtos: ElectricalVisualEdge[], isDark: boolean): Edge[] {
  return dtos.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
    type: 'electrical',
    data: {
      label: edge.label,
      emphasis: edge.emphasis,
      isDark,
    },
    selected: false,
  }));
}

function positionsFromNodes(nodes: Node[]): GraphLayoutPositions {
  const positions: GraphLayoutPositions = {};
  for (const node of nodes) {
    positions[node.id] = { x: node.position.x, y: node.position.y };
  }
  return positions;
}

function PowerRailBanner({
  rail,
  isDark,
}: {
  rail: ElectricalPowerRailVisual;
  isDark: boolean;
}) {
  const t = themeColors(isDark);
  const style: CSSProperties = {
    position: 'absolute',
    left: 24,
    right: 24,
    top: 12,
    zIndex: 5,
    pointerEvents: 'none',
    border: `1px solid ${t.border}`,
    borderRadius: 8,
    background: isDark ? 'rgba(28,36,48,0.92)' : 'rgba(255,255,255,0.92)',
    padding: '8px 12px',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    color: t.text,
    fontSize: 12,
    boxShadow: '0 1px 2px rgba(16,24,40,0.06)',
  };
  return (
    <div style={style} data-testid={`power-rail-${rail.id}`}>
      <div style={{ height: 2, flex: 1, background: '#DC6B20', borderRadius: 999 }} />
      <strong>
        {rail.nominalVoltage != null
          ? `${rail.nominalVoltage} ${rail.unit ?? 'V'} Power Rail`
          : rail.label}
      </strong>
      <div style={{ height: 2, flex: 1, background: '#DC6B20', borderRadius: 999 }} />
    </div>
  );
}

function ElectricalGraphCanvasInner({
  nodes: nodeDtos,
  edges: edgeDtos,
  powerRails = [],
  isDark,
  selectedNodeId = null,
  onSelectNode,
  onNodeDragStop,
  onViewportChange,
  fitView = true,
  testId = 'electrical-graph-canvas',
}: ElectricalGraphCanvasProps) {
  const t = themeColors(isDark);
  const nodeTypes = useMemo(() => electricalNodeTypes(), []);
  const initialNodes = useMemo(
    () => toFlowNodes(nodeDtos, selectedNodeId, isDark),
    [nodeDtos, selectedNodeId, isDark],
  );
  const initialEdges = useMemo(() => toFlowEdges(edgeDtos, isDark), [edgeDtos, isDark]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(toFlowNodes(nodeDtos, selectedNodeId, isDark));
  }, [nodeDtos, selectedNodeId, isDark, setNodes]);

  useEffect(() => {
    setEdges(toFlowEdges(edgeDtos, isDark));
  }, [edgeDtos, isDark, setEdges]);

  const handleNodeClick = useCallback(
    (_event: MouseEvent, node: Node) => onSelectNode?.(node.id),
    [onSelectNode],
  );
  const handlePaneClick = useCallback(() => onSelectNode?.(null), [onSelectNode]);
  const handleNodeDragStop: OnNodeDrag = useCallback(
    (_event, node, currentNodes) => {
      onNodeDragStop?.(positionsFromNodes(currentNodes), node.id);
    },
    [onNodeDragStop],
  );

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: t.bg }} data-testid={testId}>
      {powerRails[0] ? <PowerRailBanner rail={powerRails[0]} isDark={isDark} /> : null}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        onNodeDragStop={handleNodeDragStop}
        onMoveEnd={(_event, viewport) => onViewportChange?.(viewport)}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView={fitView}
        nodesDraggable
        elementsSelectable
        panOnDrag
        zoomOnScroll
        proOptions={{ hideAttribution: true }}
        style={{ background: t.bg }}
      >
        <Background color={t.border} gap={18} size={1} />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={() => t.cobalt}
          maskColor={isDark ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.6)'}
          style={{ background: t.surface }}
        />
      </ReactFlow>
    </div>
  );
}

export function ElectricalGraphCanvas(props: ElectricalGraphCanvasProps) {
  return (
    <ReactFlowProvider>
      <ElectricalGraphCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
