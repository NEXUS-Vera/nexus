import type { ElectricalArchitectureContent } from '@nexus/contracts';
import type {
  ElectricalPowerRailVisual,
  ElectricalVisualCategory,
  ElectricalVisualEdge,
  ElectricalVisualGraph,
  ElectricalVisualInterface,
  ElectricalVisualNode,
  ElectricalVisualStatus,
} from '../types';

type CandidateInfo = {
  candidateId: string;
  partNumber?: string;
  manufacturer?: string;
  displayName?: string;
  category?: string;
};

type AdaptOptions = {
  candidatesById?: Record<string, CandidateInfo>;
  roleCategoryById?: Record<string, string>;
  simulationSupportedIds?: Set<string>;
  simulationSurrogateIds?: Set<string>;
  simulationUnsupportedIds?: Set<string>;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' ? (value as Record<string, unknown>) : null;
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function categoryFromRoleOrNode(
  nodeType: string,
  roleCategory: string | undefined,
  candidateCategory: string | undefined,
): ElectricalVisualCategory {
  const raw = (candidateCategory || roleCategory || nodeType || '').toLowerCase();
  if (raw.includes('compute') || raw.includes('mcu') || raw === 'controller') return 'compute';
  if (raw.includes('sensor') || raw.includes('imu') || raw.includes('motion')) return 'sensor';
  if (raw.includes('communication') || raw.includes('radio') || raw.includes('wifi')) {
    return 'communication';
  }
  if (raw.includes('storage')) return 'storage';
  if (raw.includes('power') || nodeType === 'power-source' || nodeType === 'power-regulator') {
    return 'power';
  }
  if (raw.includes('actuation') || raw.includes('motor') || raw.includes('servo')) return 'actuation';
  if (raw.includes('protection') || nodeType === 'protection') return 'protection';
  if (nodeType === 'connector' || raw.includes('connector')) return 'connector';
  if (nodeType === 'junction') return 'junction';
  if (nodeType === 'external-interface' || raw.includes('external')) return 'external';
  if (nodeType === 'supporting-electronics' || raw.includes('supporting')) return 'supporting';
  if (nodeType === 'component') return 'unknown';
  return 'unknown';
}

function interfaceGroup(interfaceType: string): ElectricalVisualInterface['group'] {
  const value = interfaceType.toLowerCase();
  if (value === 'power' || value === 'ground' || value === 'supply') return 'power';
  if (value === 'i2c' || value === 'spi' || value === 'uart' || value === 'can' || value === 'usb') {
    return 'bus';
  }
  if (value === 'gpio' || value === 'pwm' || value === 'adc' || value === 'dac') return 'signal';
  if (value === 'control') return 'control';
  return 'other';
}

function interfaceSide(group: ElectricalVisualInterface['group']): 'left' | 'right' {
  return group === 'power' ? 'left' : 'right';
}

function statusForNode(
  node: Record<string, unknown>,
  nodeId: string,
  options: AdaptOptions,
): ElectricalVisualStatus {
  if (options.simulationUnsupportedIds?.has(nodeId)) return 'unsupported-simulation';
  if (options.simulationSurrogateIds?.has(nodeId)) return 'simulation-surrogate';
  if (options.simulationSupportedIds?.has(nodeId)) return 'simulation-supported';
  const implementation = String(node.implementationStatus ?? '');
  const evidence = String(node.evidenceStatus ?? '');
  const selection = String(node.selectionState ?? '');
  if (implementation === 'blocked' || selection === 'rejected') return 'blocking';
  if (implementation === 'provisional' || selection === 'awaiting-user') return 'provisional';
  if (evidence === 'unverified') return 'unverified';
  return 'normal';
}

function layoutForCategory(category: ElectricalVisualCategory, index: number): { x: number; y: number } {
  if (category === 'power') return { x: 40, y: 40 + index * 40 };
  if (category === 'sensor') return { x: 80, y: 140 + index * 180 };
  if (category === 'compute') return { x: 420, y: 180 + index * 40 };
  if (category === 'communication') return { x: 760, y: 140 + index * 160 };
  return { x: 240 + (index % 3) * 220, y: 420 + Math.floor(index / 3) * 160 };
}

export function adaptElectricalVisualGraph(
  content: ElectricalArchitectureContent | null | undefined | Record<string, unknown>,
  options: AdaptOptions = {},
): ElectricalVisualGraph {
  const record = asRecord(content);
  if (!record) return { nodes: [], edges: [], powerRails: [] };

  const sourceNodes = asArray<Record<string, unknown>>(record.nodes);
  const sourceConnections = asArray<Record<string, unknown>>(record.connections);
  const connectedInterfaceIds = new Set<string>();
  for (const connection of sourceConnections) {
    for (const key of ['fromInterfaceId', 'toInterfaceId'] as const) {
      const value = connection[key];
      if (typeof value === 'string' && value) connectedInterfaceIds.add(value);
    }
  }

  const categoryCounters: Record<string, number> = {};
  const nodes: ElectricalVisualNode[] = sourceNodes.map((node, index) => {
    const nodeId = String(node.nodeId ?? `enode_${index}`);
    const roleIds = asArray<string>(node.componentRoleIds);
    const roleCategory = roleIds
      .map((id) => options.roleCategoryById?.[id])
      .find((value): value is string => Boolean(value));
    const candidateId =
      typeof node.componentCandidateId === 'string' ? node.componentCandidateId : undefined;
    const candidate = candidateId ? options.candidatesById?.[candidateId] : undefined;
    const category = categoryFromRoleOrNode(
      String(node.nodeType ?? 'component'),
      roleCategory,
      candidate?.category,
    );
    categoryCounters[category] = (categoryCounters[category] ?? 0) + 1;
    const interfaces = asArray<Record<string, unknown>>(node.interfaces).map((iface, ifaceIndex) => {
      const interfaceId = String(iface.interfaceId ?? `iface_${ifaceIndex}`);
      const interfaceType = String(iface.interfaceType ?? 'unknown');
      const group = interfaceGroup(interfaceType);
      const label =
        typeof iface.label === 'string' && iface.label.trim()
          ? iface.label
          : interfaceType.toUpperCase();
      return {
        interfaceId,
        label,
        interfaceType,
        group,
        side: interfaceSide(group),
        status: typeof iface.status === 'string' ? iface.status : undefined,
        active: connectedInterfaceIds.has(interfaceId) || group === 'power' || group === 'bus',
      };
    });

    const title =
      candidate?.displayName ||
      (typeof node.name === 'string' ? node.name : undefined) ||
      'Electrical node';
    const subtitleParts = [
      category === 'compute' ? 'Main compute' : category === 'sensor' ? 'Sensor' : category,
      candidate?.partNumber,
    ].filter(Boolean);

    return {
      id: nodeId,
      category,
      title,
      subtitle: subtitleParts.join(' · '),
      status: statusForNode(node, nodeId, options),
      interfaces,
      componentRoleIds: roleIds,
      componentCandidateId: candidateId,
      partNumber: candidate?.partNumber,
      manufacturer: candidate?.manufacturer,
      requirementIds: asArray<string>(node.requirementIds),
      warnings: asArray<string>(node.notes).filter((note) => /warn|risk|unresolved/i.test(note)),
      position: layoutForCategory(category, categoryCounters[category] - 1),
      rawNodeType: String(node.nodeType ?? 'component'),
    };
  });

  const edges: ElectricalVisualEdge[] = sourceConnections.map((connection, index) => {
    const interfaceType = String(connection.interfaceType ?? 'unknown');
    const connectionType = String(connection.connectionType ?? 'signal');
    const status = String(connection.status ?? 'needs-resolution');
    let emphasis: ElectricalVisualEdge['emphasis'] = 'signal';
    if (connectionType === 'power' || interfaceType === 'power' || interfaceType === 'ground') {
      emphasis = 'power';
    } else if (['i2c', 'spi', 'uart', 'can', 'usb'].includes(interfaceType.toLowerCase())) {
      emphasis = 'bus';
    } else if (status === 'needs-resolution' || status === 'provisional') {
      emphasis = 'unresolved';
    }
    return {
      id: String(connection.connectionId ?? `econn_${index}`),
      source: String(connection.fromNodeId ?? ''),
      target: String(connection.toNodeId ?? ''),
      sourceHandle:
        typeof connection.fromInterfaceId === 'string' ? connection.fromInterfaceId : undefined,
      targetHandle:
        typeof connection.toInterfaceId === 'string' ? connection.toInterfaceId : undefined,
      label: interfaceType.toUpperCase(),
      connectionType,
      interfaceType,
      status,
      emphasis,
    };
  });

  const powerRails: ElectricalPowerRailVisual[] = asArray<Record<string, unknown>>(
    record.powerDomains,
  ).map((domain, index) => {
    const voltage = asRecord(domain.nominalVoltage);
    return {
      id: String(domain.powerDomainId ?? `pd_${index}`),
      label: String(domain.name ?? 'Power rail'),
      nominalVoltage: typeof voltage?.value === 'number' ? voltage.value : undefined,
      unit: typeof voltage?.unit === 'string' ? voltage.unit : 'V',
      connectedNodeIds: asArray<string>(domain.memberNodeIds ?? domain.connectedNodeIds),
      status: String(domain.status ?? 'unresolved'),
    };
  });

  return { nodes, edges, powerRails };
}
