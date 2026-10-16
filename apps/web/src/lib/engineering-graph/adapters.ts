import type {
  ElectricalArchitectureContent,
  FunctionalArchitectureContent,
  PhysicalArchitectureContent,
} from '@nexus/contracts';
import type { EngineeringGraphDto, EngineeringGraphEdgeDto, EngineeringGraphNodeDto } from './types';

function gridPosition(index: number, cols = 3): { x: number; y: number } {
  const col = index % cols;
  const row = Math.floor(index / cols);
  return { x: 80 + col * 220, y: 60 + row * 140 };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' ? (value as Record<string, unknown>) : null;
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

/** Safe empty graph for missing / loading / unavailable architecture content. */
export function emptyEngineeringGraph(): EngineeringGraphDto {
  return { nodes: [], edges: [] };
}

export function adaptFunctionalArchitecture(
  content: FunctionalArchitectureContent | null | undefined | Record<string, unknown>,
): EngineeringGraphDto {
  const record = asRecord(content);
  if (!record) return emptyEngineeringGraph();
  const sourceNodes = asArray<FunctionalArchitectureContent['nodes'][number]>(record.nodes);
  const sourceEdges = asArray<FunctionalArchitectureContent['edges'][number]>(record.edges);

  const nodes: EngineeringGraphNodeDto[] = sourceNodes.map((node, index) => ({
    id: String(node.nodeId ?? `node_${index}`),
    label: String(node.name ?? 'Untitled'),
    subtitle: String(node.functionalType ?? ''),
    kind: 'functional-node',
    semanticType: String(node.functionalType ?? 'processing'),
    position: gridPosition(index),
    data: {
      responsibilities: asArray<string>(node.responsibilities),
      satisfiesRequirementIds: asArray<string>(node.satisfiesRequirementIds),
      inputs: asArray<string>(node.inputs),
      outputs: asArray<string>(node.outputs),
    },
  }));

  const edges: EngineeringGraphEdgeDto[] = sourceEdges.map((edge, index) => ({
    id: String(edge.edgeId ?? `edge_${index}`),
    source: String(edge.fromNodeId ?? ''),
    target: String(edge.toNodeId ?? ''),
    label: String(edge.flowType ?? ''),
    edgeType: String(edge.flowType ?? 'data'),
  }));

  return { nodes, edges };
}

export function adaptElectricalArchitecture(
  content: ElectricalArchitectureContent | null | undefined | Record<string, unknown>,
): EngineeringGraphDto {
  const record = asRecord(content);
  if (!record) return emptyEngineeringGraph();
  const sourceNodes = asArray<ElectricalArchitectureContent['nodes'][number]>(record.nodes);
  const sourceConnections = asArray<ElectricalArchitectureContent['connections'][number]>(
    record.connections,
  );

  const nodes: EngineeringGraphNodeDto[] = sourceNodes.map((node, index) => ({
    id: String(node.nodeId ?? `enode_${index}`),
    label: String(node.name ?? 'Untitled'),
    subtitle: `${String(node.nodeType ?? 'component')} · ${String(node.implementationStatus ?? 'unresolved')}`,
    kind: 'electrical-node',
    semanticType: String(node.nodeType ?? 'component'),
    position: gridPosition(index),
    data: {
      nodeType: node.nodeType,
      implementationStatus: node.implementationStatus,
      evidenceStatus: node.evidenceStatus,
      selectionState: node.selectionState,
      componentRoleIds: asArray<string>(node.componentRoleIds),
      functionalArchitectureNodeIds: asArray<string>(node.functionalArchitectureNodeIds),
      interfaces: asArray<unknown>(node.interfaces),
      requirementIds: asArray<string>(node.requirementIds),
      notes: node.notes,
    },
  }));

  const edges: EngineeringGraphEdgeDto[] = sourceConnections.map((connection, index) => ({
    id: String(connection.connectionId ?? `econn_${index}`),
    source: String(connection.fromNodeId ?? ''),
    target: String(connection.toNodeId ?? ''),
    label: String(connection.interfaceType ?? ''),
    edgeType: String(connection.connectionType ?? 'signal'),
  }));

  return { nodes, edges };
}

export function adaptPhysicalArchitecture(
  content: PhysicalArchitectureContent | null | undefined | Record<string, unknown>,
): EngineeringGraphDto {
  const record = asRecord(content);
  if (!record) return emptyEngineeringGraph();
  const sourceNodes = asArray<PhysicalArchitectureContent['nodes'][number]>(record.nodes);
  const sourceRels = asArray<PhysicalArchitectureContent['relationships'][number]>(
    record.relationships,
  );

  const nodes: EngineeringGraphNodeDto[] = sourceNodes.map((node, index) => ({
    id: String(node.nodeId ?? `pnode_${index}`),
    label: String(node.name ?? 'Untitled'),
    subtitle: `${String(node.nodeType ?? 'module')} · ${String(node.placementStatus ?? 'unresolved')}`,
    kind: 'physical-node',
    semanticType: String(node.nodeType ?? 'module'),
    position: gridPosition(index),
    data: {
      nodeType: node.nodeType,
      placementStatus: node.placementStatus,
      qualitativePlacement: node.qualitativePlacement,
      zoneId: node.zoneId,
      electricalNodeIds: asArray<string>(node.electricalNodeIds),
      constraints: asArray<string>(node.constraints),
      notes: node.notes,
    },
  }));

  const edges: EngineeringGraphEdgeDto[] = sourceRels.map((rel, index) => ({
    id: String(rel.relationshipId ?? `prel_${index}`),
    source: String(rel.fromNodeId ?? ''),
    target: String(rel.toNodeId ?? ''),
    label: String(rel.relationshipType ?? ''),
    edgeType: String(rel.relationshipType ?? 'adjacent-to'),
  }));

  return { nodes, edges };
}
