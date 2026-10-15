import { useCallback, useEffect, useMemo, type CSSProperties, type MouseEvent } from 'react';
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  Handle,
  Position,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
  type OnNodeDrag,
  type Viewport,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { themeColors } from '../theme';
import type { EngineeringGraphEdgeDto, EngineeringGraphNodeDto, GraphLayoutPositions } from './types';

export type EngineeringGraphCanvasProps = {
  nodes: EngineeringGraphNodeDto[];
  edges: EngineeringGraphEdgeDto[];
  isDark: boolean;
  selectedNodeId?: string | null;
  onSelectNode?: (id: string | null) => void;
  /** Called when a node drag ends — layout only; never semantic artifact revision. */
  onNodeDragStop?: (positions: GraphLayoutPositions, nodeId: string) => void;
  onViewportChange?: (viewport: Viewport) => void;
  fitView?: boolean;
  testId?: string;
};

type EngNodeData = {
  label: string;
  subtitle?: string;
  kind: string;
  semanticType?: string;
  selected: boolean;
  isDark: boolean;
  payload: Record<string, unknown>;
};

function EngineeringNode({ data }: NodeProps<Node<EngNodeData>>) {
  const t = themeColors(data.isDark);
  const active = data.selected;
  const style: CSSProperties = {
    minWidth: 140,
    maxWidth: 200,
    padding: '10px 12px',
    borderRadius: 8,
    border: `2px solid ${active ? t.cobalt : t.border}`,
    background: active ? t.cobaltSelected : t.surface,
    boxShadow: active ? `0 0 0 1px ${t.cobalt}` : 'none',
    fontSize: 12,
    color: t.text,
  };

  return (
    <div style={style} data-testid={`eng-node-${(data as EngNodeData).label}`}>
      <Handle type="target" position={Position.Left} style={{ background: t.cobalt }} />
      <div style={{ fontWeight: 600, lineHeight: 1.3 }}>{data.label}</div>
      {data.subtitle ? (
        <div style={{ marginTop: 4, fontSize: 10, color: t.textMuted }}>{data.subtitle}</div>
      ) : null}
      <Handle type="source" position={Position.Right} style={{ background: t.cobalt }} />
    </div>
  );
}

const nodeTypes = { engineering: EngineeringNode };

function toFlowNodes(
  dtos: EngineeringGraphNodeDto[],
  selectedNodeId: string | null | undefined,
  isDark: boolean,
): Node<EngNodeData>[] {
  return dtos.map((node) => ({
    id: node.id,
    type: 'engineering',
    position: node.position ?? { x: 0, y: 0 },
    data: {
      label: node.label,
      subtitle: node.subtitle,
      kind: node.kind,
      semanticType: node.semanticType,
      selected: selectedNodeId === node.id,
      isDark,
      payload: node.data,
    },
    selected: selectedNodeId === node.id,
  }));
}

function toFlowEdges(dtos: EngineeringGraphEdgeDto[], isDark: boolean): Edge[] {
  const t = themeColors(isDark);
  return dtos.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.label,
    type: 'smoothstep',
    style: { stroke: t.border, strokeWidth: 2 },
    labelStyle: { fontSize: 10, fill: t.textMuted },
  }));
}

function positionsFromNodes(nodes: Node[]): GraphLayoutPositions {
  const positions: GraphLayoutPositions = {};
  for (const node of nodes) {
    positions[node.id] = { x: node.position.x, y: node.position.y };
  }
  return positions;
}

function EngineeringGraphCanvasInner({
  nodes: nodeDtos,
  edges: edgeDtos,
  isDark,
  selectedNodeId = null,
  onSelectNode,
  onNodeDragStop,
  onViewportChange,
  fitView = true,
  testId = 'engineering-graph-canvas',
}: EngineeringGraphCanvasProps) {
  const t = themeColors(isDark);
  const initialNodes = useMemo(
    () => toFlowNodes(nodeDtos, selectedNodeId, isDark),
    // Intentionally rebuild when DTO identity / selection / theme changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    (_event: MouseEvent, node: Node) => {
      onSelectNode?.(node.id);
    },
    [onSelectNode],
  );

  const handlePaneClick = useCallback(() => {
    onSelectNode?.(null);
  }, [onSelectNode]);

  const handleNodeDragStop: OnNodeDrag = useCallback(
    (_event, _node, currentNodes) => {
      // Layout-only callback — callers must not propose/accept artifact revisions here.
      onNodeDragStop?.(positionsFromNodes(currentNodes), _node.id);
    },
    [onNodeDragStop],
  );

  return (
    <div style={{ width: '100%', height: '100%', background: t.bg }} data-testid={testId}>
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

export function EngineeringGraphCanvas(props: EngineeringGraphCanvasProps) {
  return (
    <ReactFlowProvider>
      <EngineeringGraphCanvasInner {...props} />
    </ReactFlowProvider>
  );
}

/** Test/helper: build layout positions from nodes after a drag stop without artifact commands. */
export function layoutPositionsAfterDrag(
  nodes: Array<{ id: string; position: { x: number; y: number } }>,
): GraphLayoutPositions {
  return positionsFromNodes(nodes as Node[]);
}
