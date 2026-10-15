/** Frontend-only Electrical visual DTOs — not persisted as canonical contracts. */

export type ElectricalVisualCategory =
  | 'compute'
  | 'sensor'
  | 'communication'
  | 'storage'
  | 'power'
  | 'actuation'
  | 'protection'
  | 'connector'
  | 'junction'
  | 'supporting'
  | 'external'
  | 'unknown';

export type ElectricalVisualStatus =
  | 'normal'
  | 'selected'
  | 'provisional'
  | 'unverified'
  | 'at-risk'
  | 'blocking'
  | 'simulation-supported'
  | 'simulation-surrogate'
  | 'unsupported-simulation';

export type ElectricalInterfaceSide = 'left' | 'right';

export type ElectricalVisualInterface = {
  interfaceId: string;
  label: string;
  interfaceType: string;
  group: 'power' | 'bus' | 'signal' | 'control' | 'other';
  side: ElectricalInterfaceSide;
  status?: string;
  active: boolean;
};

export type ElectricalVisualNode = {
  id: string;
  category: ElectricalVisualCategory;
  title: string;
  subtitle: string;
  status: ElectricalVisualStatus;
  interfaces: ElectricalVisualInterface[];
  componentRoleIds: string[];
  componentCandidateId?: string;
  partNumber?: string;
  manufacturer?: string;
  requirementIds: string[];
  warnings: string[];
  position?: { x: number; y: number };
  rawNodeType: string;
};

export type ElectricalVisualEdge = {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  label: string;
  connectionType: string;
  interfaceType: string;
  status: string;
  emphasis: 'signal' | 'power' | 'bus' | 'unresolved' | 'warning';
};

export type ElectricalPowerRailVisual = {
  id: string;
  label: string;
  nominalVoltage?: number;
  unit?: string;
  connectedNodeIds: string[];
  status: string;
};

export type ElectricalVisualGraph = {
  nodes: ElectricalVisualNode[];
  edges: ElectricalVisualEdge[];
  powerRails: ElectricalPowerRailVisual[];
};

export type SimulationMappingType = 'exact' | 'equivalent' | 'surrogate' | 'unsupported';

export type SimulationVisualPin = {
  sourcePin: string;
  providerPin: string;
};

export type SimulationVisualNode = {
  id: string;
  nexusEntityId?: string;
  nexusTitle: string;
  nexusPartNumber?: string;
  providerPartId: string;
  providerPartType: string;
  mappingType: SimulationMappingType;
  pins: SimulationVisualPin[];
  position?: { x: number; y: number };
};

export type SimulationVisualConnection = {
  id: string;
  source: string;
  target: string;
  sourcePin: string;
  targetPin: string;
  label: string;
};

export type SimulationVisualGraph = {
  providerId: string;
  nodes: SimulationVisualNode[];
  connections: SimulationVisualConnection[];
  surrogateUsed: boolean;
  findings: Array<{ findingId: string; message: string; mappingType: string }>;
};

export type ElectricalWorkspaceMode = 'design' | 'simulation';
