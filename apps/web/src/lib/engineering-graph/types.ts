/** Canonical engineering-graph DTOs — adapters must not emit React Flow types. */

export type EngineeringGraphNodeDto = {
  id: string;
  label: string;
  subtitle?: string;
  kind: string;
  semanticType?: string;
  position?: { x: number; y: number };
  data: Record<string, unknown>;
};

export type EngineeringGraphEdgeDto = {
  id: string;
  source: string;
  target: string;
  label?: string;
  edgeType?: string;
};

export type EngineeringGraphDto = {
  nodes: EngineeringGraphNodeDto[];
  edges: EngineeringGraphEdgeDto[];
};

export type GraphLayoutPositions = Record<string, { x: number; y: number }>;

export type GraphLayoutViewport = {
  x: number;
  y: number;
  zoom: number;
};

/** Frontend-only layout persistence payload (not an artifact revision). */
export type GraphLayoutState = {
  viewport?: GraphLayoutViewport;
  positions: GraphLayoutPositions;
  updatedAt: string;
};
