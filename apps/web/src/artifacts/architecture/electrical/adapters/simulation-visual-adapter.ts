import type {
  SimulationMappingType,
  SimulationVisualConnection,
  SimulationVisualGraph,
  SimulationVisualNode,
} from '../types';

type PreviewMapping = {
  providerPartId: string;
  providerPartType: string;
  mappingType?: string;
  pinProfile?: Array<{ sourcePin?: string; providerPin?: string }>;
  sourceReferences?: Array<{
    entityId?: string;
    entityType?: string;
    displayLabel?: string;
    artifactType?: string;
  }>;
};

type PreviewPayload = {
  providerId?: string;
  surrogateUsed?: boolean;
  mappings?: PreviewMapping[];
  connections?: Array<{
    id?: string;
    sourcePartId?: string;
    targetPartId?: string;
    sourcePin?: string;
    targetPin?: string;
    label?: string;
  }>;
  findings?: Array<{ findingId?: string; message?: string; mappingType?: string }>;
};

function asMappingType(value: string | undefined): SimulationMappingType {
  if (value === 'exact' || value === 'equivalent' || value === 'surrogate') return value;
  return 'unsupported';
}

export function adaptSimulationVisualGraph(preview: PreviewPayload | null | undefined): SimulationVisualGraph {
  if (!preview) {
    return {
      providerId: 'unknown',
      nodes: [],
      connections: [],
      surrogateUsed: false,
      findings: [],
    };
  }

  const nodes: SimulationVisualNode[] = (preview.mappings ?? []).map((mapping, index) => {
    const candidateRef = (mapping.sourceReferences ?? []).find(
      (ref) => ref.entityType === 'component-candidate',
    );
    const electricalRef = (mapping.sourceReferences ?? []).find(
      (ref) => ref.entityType === 'electrical-node',
    );
    const isMcu = mapping.providerPartType.includes('esp32');
    return {
      id: mapping.providerPartId || `part_${index}`,
      nexusEntityId: electricalRef?.entityId,
      nexusTitle: candidateRef?.displayLabel || electricalRef?.displayLabel || 'Nexus component',
      nexusPartNumber: undefined,
      providerPartId: mapping.providerPartId,
      providerPartType: mapping.providerPartType,
      mappingType: asMappingType(mapping.mappingType),
      pins: (mapping.pinProfile ?? []).map((pin) => ({
        sourcePin: String(pin.sourcePin ?? ''),
        providerPin: String(pin.providerPin ?? ''),
      })),
      position: isMcu ? { x: 80, y: 120 } : { x: 480, y: 140 },
    };
  });

  const connections: SimulationVisualConnection[] = (preview.connections ?? []).map(
    (connection, index) => ({
      id: connection.id || `sim_conn_${index}`,
      source: String(connection.sourcePartId ?? ''),
      target: String(connection.targetPartId ?? ''),
      sourcePin: String(connection.sourcePin ?? ''),
      targetPin: String(connection.targetPin ?? ''),
      label: String(connection.label ?? `${connection.sourcePin}→${connection.targetPin}`),
    }),
  );

  return {
    providerId: preview.providerId || 'wokwi',
    nodes,
    connections,
    surrogateUsed: Boolean(preview.surrogateUsed),
    findings: (preview.findings ?? []).map((finding, index) => ({
      findingId: finding.findingId || `finding_${index}`,
      message: finding.message || 'Finding',
      mappingType: finding.mappingType || 'unsupported',
    })),
  };
}
