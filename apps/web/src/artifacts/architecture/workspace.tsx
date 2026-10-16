import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from 'react';
import type {
  Artifact,
  ArtifactCommand,
  ArtifactCommandResult,
  ElectricalArchitectureContent,
  FunctionalArchitectureContent,
  PhysicalArchitectureContent,
  WorkspaceDescriptor,
  WorkspaceDraftState,
} from '@nexus/contracts';
import {
  ApiClientError,
  createWorkspace,
  ensureLayeredArchitecture,
  getWorkspace,
  submitArtifactCommand,
} from '../../api/client';
import { EngineeringGraphCanvas } from '../../lib/engineering-graph/EngineeringGraphCanvas';
import {
  adaptElectricalArchitecture,
  adaptFunctionalArchitecture,
  adaptPhysicalArchitecture,
} from '../../lib/engineering-graph/adapters';
import { EditSessionHistory } from '../../lib/engineering-graph/edit-session-history';
import {
  applyLayoutPositions,
  loadArchitectureLayout,
  resetArchitectureLayout,
  saveArchitectureLayout,
} from '../../lib/engineering-graph/layout-persistence';
import type { GraphLayoutPositions, GraphLayoutViewport } from '../../lib/engineering-graph/types';
import { themeColors } from '../../lib/theme';
import { ElectricalGraphCanvas } from './electrical/ElectricalGraphCanvas';
import { ElectricalModeTabs } from './electrical/ElectricalModeTabs';
import { ElectricalStatusBar } from './electrical/ElectricalStatusBar';
import { adaptElectricalVisualGraph } from './electrical/adapters/electrical-visual-adapter';
import { ElectricalSimulationView } from './electrical/simulation/ElectricalSimulationView';
import type { ElectricalWorkspaceMode } from './electrical/types';
import {
  ARCHITECTURE_VIEW_ORDER,
  ARCHITECTURE_VIEW_REGISTRY,
  type ArchitectureViewId,
  artifactTypeFromView,
} from './views';

type ArchitectureArtifact =
  | Extract<Artifact, { artifactType: 'functional-architecture' }>
  | Extract<Artifact, { artifactType: 'electrical-architecture' }>
  | Extract<Artifact, { artifactType: 'physical-architecture' }>;

type ArchitectureDraftContent =
  | FunctionalArchitectureContent
  | ElectricalArchitectureContent
  | PhysicalArchitectureContent;

type WorkspaceEnvelope = {
  workspace: WorkspaceDescriptor;
  draft?: WorkspaceDraftState;
};

export type ArchitectureSemanticOp =
  | { type: 'rename-node'; nodeId: string; name: string }
  | { type: 'delete-node'; nodeId: string }
  /** Explicit deletion after impact preview; draft-only — accept triggers regenerate. */
  | { type: 'remove-and-reconcile'; nodeId: string }
  | {
      type: 'add-node';
      name?: string;
      functionalType?: FunctionalArchitectureContent['nodes'][number]['functionalType'];
    }
  | {
      type: 'add-edge';
      fromNodeId: string;
      toNodeId: string;
      flowType?: FunctionalArchitectureContent['edges'][number]['flowType'];
      description?: string;
    }
  | { type: 'delete-edge'; edgeId: string }
  | {
      type: 'change-edge-flow';
      edgeId: string;
      flowType: FunctionalArchitectureContent['edges'][number]['flowType'];
    };

export type ElectricalSemanticOp =
  | { type: 'add-supporting-node'; name?: string }
  | { type: 'delete-supporting-node'; nodeId: string }
  | {
      type: 'add-connection';
      fromNodeId: string;
      toNodeId: string;
      connectionType?: ElectricalArchitectureContent['connections'][number]['connectionType'];
      interfaceType?: ElectricalArchitectureContent['connections'][number]['interfaceType'];
      status?: ElectricalArchitectureContent['connections'][number]['status'];
      description?: string;
    }
  | { type: 'delete-connection'; connectionId: string }
  | {
      type: 'change-connection';
      connectionId: string;
      connectionType?: ElectricalArchitectureContent['connections'][number]['connectionType'];
      interfaceType?: ElectricalArchitectureContent['connections'][number]['interfaceType'];
      status?: ElectricalArchitectureContent['connections'][number]['status'];
    }
  | {
      type: 'mark-connection-status';
      connectionId: string;
      status: ElectricalArchitectureContent['connections'][number]['status'];
    };

export type PhysicalSemanticOp =
  | {
      type: 'add-entity';
      name?: string;
      nodeType?: PhysicalArchitectureContent['nodes'][number]['nodeType'];
      qualitativePlacement?: string;
    }
  | { type: 'delete-entity'; nodeId: string }
  | {
      type: 'add-zone';
      name?: string;
      zoneKind?: PhysicalArchitectureContent['zones'][number]['zoneKind'];
    }
  | {
      type: 'assign-zone';
      nodeId: string;
      zoneId: string;
      qualitativePlacement?: string;
    }
  | {
      type: 'add-relationship';
      fromNodeId: string;
      toNodeId: string;
      relationshipType?: PhysicalArchitectureContent['relationships'][number]['relationshipType'];
    }
  | { type: 'delete-relationship'; relationshipId: string }
  | { type: 'delete-zone'; zoneId: string }
  | {
      type: 'change-relationship';
      relationshipId: string;
      relationshipType?: PhysicalArchitectureContent['relationships'][number]['relationshipType'];
      status?: PhysicalArchitectureContent['relationships'][number]['status'];
    }
  | {
      type: 'edit-placement';
      nodeId: string;
      qualitativePlacement?: string;
      placementStatus?: PhysicalArchitectureContent['nodes'][number]['placementStatus'];
    };

type DeletionImpactPayload = {
  blocking?: boolean;
  summary?: string;
  affectedComponentRoleIds?: string[];
  affectedElectricalNodeIds?: string[];
};

type Props = {
  projectId: string;
  viewId: ArchitectureViewId;
  artifact?: ArchitectureArtifact;
  componentPlan?: Extract<Artifact, { artifactType: 'component-plan' }>;
  isDark: boolean;
  selectedNodeId?: string | null;
  onSelectNode?: (id: string | null) => void;
  onChangeView?: (viewId: ArchitectureViewId) => void;
  electricalMode?: ElectricalWorkspaceMode;
  onChangeElectricalMode?: (mode: ElectricalWorkspaceMode) => void;
  onAskVera?: () => void;
  onCommandResult?: (result: ArtifactCommandResult) => void;
  /** Refresh project state after ensure-layered-architecture or similar. */
  onProjectStateRefresh?: () => void;
  /** Optional parent-owned draft mutator for System semantic edits. */
  onSemanticPatch?: (
    mutator: (content: FunctionalArchitectureContent) => FunctionalArchitectureContent,
  ) => void;
};

type ConfirmDialogState = {
  title: string;
  summary?: string;
  confirmLabel?: string;
  /** When false, only a dismiss action is shown (alert replacement). */
  destructive?: boolean;
  onConfirm?: () => void;
};

type DraftFormState =
  | {
      kind: 'add-node';
      name: string;
      functionalType: FunctionalArchitectureContent['nodes'][number]['functionalType'];
    }
  | { kind: 'rename-node'; nodeId: string; name: string }
  | {
      kind: 'add-edge';
      fromNodeId: string;
      toNodeId: string;
      flowType: FunctionalArchitectureContent['edges'][number]['flowType'];
    }
  | {
      kind: 'change-edge-flow';
      edgeId: string;
      flowType: FunctionalArchitectureContent['edges'][number]['flowType'];
    }
  | { kind: 'delete-edge'; edgeId: string }
  | { kind: 'add-supporting-node'; name: string }
  | {
      kind: 'add-connection';
      fromNodeId: string;
      toNodeId: string;
      connectionType: ElectricalArchitectureContent['connections'][number]['connectionType'];
      interfaceType: ElectricalArchitectureContent['connections'][number]['interfaceType'];
    }
  | { kind: 'delete-connection'; connectionId: string }
  | {
      kind: 'change-connection-type';
      connectionId: string;
      connectionType: ElectricalArchitectureContent['connections'][number]['connectionType'];
    }
  | {
      kind: 'change-interface-type';
      connectionId: string;
      interfaceType: ElectricalArchitectureContent['connections'][number]['interfaceType'];
    }
  | {
      kind: 'mark-connection-status';
      connectionId: string;
      status: ElectricalArchitectureContent['connections'][number]['status'];
    }
  | {
      kind: 'add-entity';
      name: string;
      nodeType: PhysicalArchitectureContent['nodes'][number]['nodeType'];
    }
  | {
      kind: 'add-zone';
      name: string;
      zoneKind: PhysicalArchitectureContent['zones'][number]['zoneKind'];
    }
  | { kind: 'delete-zone'; zoneId: string }
  | { kind: 'assign-zone'; nodeId: string; zoneId: string }
  | {
      kind: 'add-relationship';
      fromNodeId: string;
      toNodeId: string;
      relationshipType: PhysicalArchitectureContent['relationships'][number]['relationshipType'];
    }
  | {
      kind: 'change-relationship';
      relationshipId: string;
      relationshipType: PhysicalArchitectureContent['relationships'][number]['relationshipType'];
    }
  | { kind: 'delete-relationship'; relationshipId: string }
  | {
      kind: 'edit-placement';
      nodeId: string;
      qualitativePlacement: string;
      placementStatus: PhysicalArchitectureContent['nodes'][number]['placementStatus'];
    };

const FLOW_TYPES = ['data', 'control', 'power', 'user-input', 'physical-output'] as const;
const FUNCTIONAL_TYPES = [
  'input',
  'sensing',
  'processing',
  'control',
  'storage',
  'communication',
  'power',
  'output',
  'actuation',
  'analysis',
  'user-interface',
  'external-system',
] as const;
const CONNECTION_TYPES = [
  'signal',
  'bus',
  'power',
  'ground',
  'communication',
  'control',
  'other',
] as const;
const INTERFACE_TYPES = [
  'analog',
  'gpio',
  'i2c',
  'spi',
  'uart',
  'can',
  'usb',
  'ethernet',
  'pwm',
  'power',
  'ground',
  'other',
  'unknown',
] as const;
const CONNECTION_STATUSES = [
  'unresolved',
  'provisional',
  'resolved',
  'needs-resolution',
] as const;
const PHYSICAL_NODE_TYPES = [
  'assembly',
  'board',
  'module',
  'sensor',
  'actuator',
  'power-source',
  'connector',
  'enclosure',
  'mount',
  'external-system',
  'zone',
] as const;
const ZONE_KINDS = [
  'enclosure',
  'chassis',
  'external-sensing',
  'power',
  'user-interface',
  'other',
  'unknown',
] as const;
const RELATIONSHIP_TYPES = [
  'mounted-on',
  'inside',
  'attached-to',
  'adjacent-to',
  'connected-to',
  'exposed-to',
  'isolated-from',
] as const;
const PLACEMENT_STATUSES = ['placed', 'unresolved', 'provisional', 'unknown'] as const;

function isFunctionalDraftContent(
  content: ArchitectureDraftContent | null | undefined,
): content is FunctionalArchitectureContent {
  if (!content || typeof content !== 'object') return false;
  const record = content as unknown as Record<string, unknown>;
  if ('requirementCoverage' in record) return true;
  return Array.isArray(record.edges) && !('connections' in record);
}

function isElectricalDraftContent(
  content: ArchitectureDraftContent | null | undefined,
): content is ElectricalArchitectureContent {
  if (!content || typeof content !== 'object') return false;
  return Array.isArray((content as ElectricalArchitectureContent).connections);
}

function isPhysicalDraftContent(
  content: ArchitectureDraftContent | null | undefined,
): content is PhysicalArchitectureContent {
  if (!content || typeof content !== 'object') return false;
  return Array.isArray((content as PhysicalArchitectureContent).relationships);
}

function fieldStyle(t: ReturnType<typeof themeColors>): CSSProperties {
  return {
    width: '100%',
    fontSize: 12,
    padding: '6px 8px',
    borderRadius: 6,
    border: `1px solid ${t.border}`,
    background: t.bg,
    color: t.text,
    boxSizing: 'border-box',
  };
}

function newCommandId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `cmd_${crypto.randomUUID().replace(/-/g, '').slice(0, 24)}`;
  }
  return `cmd_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

function newId(prefix: string): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${prefix}${crypto.randomUUID().replace(/-/g, '').slice(0, 24)}`;
  }
  return `${prefix}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

function userActor() {
  return {
    schemaVersion: '1.0.0' as const,
    actorId: 'user_local',
    actorType: 'user' as const,
  };
}

function unwrapWorkspace(payload: unknown): WorkspaceEnvelope | null {
  if (!payload || typeof payload !== 'object') return null;
  const record = payload as Record<string, unknown>;
  if (record.workspace && typeof record.workspace === 'object') {
    return {
      workspace: record.workspace as WorkspaceDescriptor,
      draft: record.draft as WorkspaceDraftState | undefined,
    };
  }
  if (typeof record.workspaceId === 'string') {
    return { workspace: record as unknown as WorkspaceDescriptor };
  }
  return null;
}

function isLeaseHeldError(err: unknown): boolean {
  if (err instanceof ApiClientError) {
    return err.body?.error.code === 'DRAFT_EDIT_LEASE_HELD';
  }
  return false;
}

function isLeaseHeldResult(result: ArtifactCommandResult): boolean {
  return (
    result.status === 'failed' && result.error?.code === 'DRAFT_EDIT_LEASE_HELD'
  );
}

export function applySemanticOp(
  content: FunctionalArchitectureContent,
  op: ArchitectureSemanticOp,
): FunctionalArchitectureContent {
  if (op.type === 'rename-node') {
    return {
      ...content,
      nodes: content.nodes.map((node) =>
        node.nodeId === op.nodeId ? { ...node, name: op.name } : node,
      ) as FunctionalArchitectureContent['nodes'],
    };
  }
  if (op.type === 'delete-node' || op.type === 'remove-and-reconcile') {
    const nodes = content.nodes.filter((node) => node.nodeId !== op.nodeId);
    const edges = content.edges.filter(
      (edge) => edge.fromNodeId !== op.nodeId && edge.toNodeId !== op.nodeId,
    );
    if (nodes.length < 1) return content;
    const covered = new Set<string>();
    for (const node of nodes) {
      for (const id of node.satisfiesRequirementIds) covered.add(id);
    }
    const coveredIds = [...covered];
    return {
      ...content,
      nodes: nodes as FunctionalArchitectureContent['nodes'],
      edges: (edges.length >= 1 ? edges : content.edges.slice(0, 1)) as FunctionalArchitectureContent['edges'],
      requirementCoverage: {
        coveredRequirementIds: (coveredIds.length
          ? coveredIds
          : content.requirementCoverage.coveredRequirementIds) as FunctionalArchitectureContent['requirementCoverage']['coveredRequirementIds'],
      },
    };
  }
  if (op.type === 'add-edge') {
    const edge = {
      edgeId: newId('edge_'),
      fromNodeId: op.fromNodeId,
      toNodeId: op.toNodeId,
      flowType: op.flowType ?? 'data',
      description: op.description?.trim() || 'User-authored functional flow',
    };
    return {
      ...content,
      edges: [...content.edges, edge] as FunctionalArchitectureContent['edges'],
    };
  }
  if (op.type === 'delete-edge') {
    const edges = content.edges.filter((edge) => edge.edgeId !== op.edgeId);
    if (edges.length < 1) return content;
    return {
      ...content,
      edges: edges as FunctionalArchitectureContent['edges'],
    };
  }
  if (op.type === 'change-edge-flow') {
    return {
      ...content,
      edges: content.edges.map((edge) =>
        edge.edgeId === op.edgeId ? { ...edge, flowType: op.flowType } : edge,
      ) as FunctionalArchitectureContent['edges'],
    };
  }
  const name = op.name?.trim() || 'New functional block';
  const functionalType = op.functionalType ?? 'processing';
  const nodeId = newId('node_');
  const nextNode = {
    nodeId,
    name,
    functionalType,
    responsibilities: ['Describe responsibilities'] as [string, ...string[]],
    satisfiesRequirementIds: content.requirementCoverage.coveredRequirementIds.slice(0, 1) as [
      string,
      ...string[],
    ],
  };
  return {
    ...content,
    nodes: [...content.nodes, nextNode] as FunctionalArchitectureContent['nodes'],
  };
}

export function recomputeCoverage(
  content: FunctionalArchitectureContent,
): FunctionalArchitectureContent {
  const covered = new Set<string>();
  for (const node of content.nodes) {
    for (const id of node.satisfiesRequirementIds) covered.add(id);
  }
  const ids = [...covered];
  return {
    ...content,
    requirementCoverage: {
      coveredRequirementIds: (ids.length
        ? ids
        : content.requirementCoverage.coveredRequirementIds) as FunctionalArchitectureContent['requirementCoverage']['coveredRequirementIds'],
    },
  };
}

export function applyElectricalSemanticOp(
  content: ElectricalArchitectureContent,
  op: ElectricalSemanticOp,
): ElectricalArchitectureContent {
  let nodes = [...content.nodes];
  let connections = [...content.connections];

  if (op.type === 'add-supporting-node') {
    nodes = [
      ...nodes,
      {
        nodeId: newId('enode_'),
        name: op.name?.trim() || 'Supporting electronics',
        nodeType: 'supporting-electronics',
        functionalArchitectureNodeIds: [],
        componentRoleIds: [],
        implementationStatus: 'unresolved',
        evidenceStatus: 'unverified',
        selectionState: 'none',
        interfaces: [
          {
            interfaceId: newId('eiface_'),
            interfaceType: 'unknown',
            direction: 'unknown',
            status: 'unresolved',
            label: 'unimplemented',
            provenance: {
              schemaVersion: '1.0.0',
              sourceType: 'user',
              notes: 'User-authored supporting Electrical node.',
            },
          },
        ],
        requirementIds: [],
        notes: 'User-authored supporting node; not a Component selection.',
      },
    ];
  } else if (op.type === 'delete-supporting-node') {
    const target = nodes.find((n) => n.nodeId === op.nodeId);
    if (!target) return content;
    if (target.componentRoleIds.length > 0) {
      throw new Error(
        'Cannot delete Electrical implementation bound to a Component Role; change selection in Component Plan instead.',
      );
    }
    nodes = nodes.filter((n) => n.nodeId !== op.nodeId);
    connections = connections.filter(
      (c) => c.fromNodeId !== op.nodeId && c.toNodeId !== op.nodeId,
    );
  } else if (op.type === 'add-connection') {
    connections = [
      ...connections,
      {
        connectionId: newId('econn_'),
        fromNodeId: op.fromNodeId,
        toNodeId: op.toNodeId,
        connectionType: op.connectionType ?? 'signal',
        interfaceType: op.interfaceType ?? 'unknown',
        status: op.status ?? 'needs-resolution',
        description: op.description ?? 'User-authored Electrical connection',
        provisionalReason: 'User-proposed; verify interface compatibility.',
        provenance: { schemaVersion: '1.0.0', sourceType: 'user' },
      },
    ];
  } else if (op.type === 'delete-connection') {
    connections = connections.filter((c) => c.connectionId !== op.connectionId);
  } else if (op.type === 'change-connection') {
    connections = connections.map((conn) => {
      if (conn.connectionId !== op.connectionId) return conn;
      return {
        ...conn,
        ...(op.connectionType != null ? { connectionType: op.connectionType } : {}),
        ...(op.interfaceType != null ? { interfaceType: op.interfaceType } : {}),
        ...(op.status != null ? { status: op.status } : {}),
        provenance: {
          schemaVersion: '1.0.0' as const,
          sourceType: 'user' as const,
          notes: 'User edited connection semantics.',
        },
      };
    });
  } else if (op.type === 'mark-connection-status') {
    connections = connections.map((conn) =>
      conn.connectionId === op.connectionId ? { ...conn, status: op.status } : conn,
    );
  }

  return {
    ...content,
    nodes,
    connections,
    coverageSummary: {
      ...content.coverageSummary,
      unresolvedConnectionCount: connections.filter((c) =>
        ['unresolved', 'needs-resolution', 'unknown'].includes(c.status),
      ).length,
    },
  };
}

export function applyPhysicalSemanticOp(
  content: PhysicalArchitectureContent,
  op: PhysicalSemanticOp,
): PhysicalArchitectureContent {
  let nodes = [...content.nodes];
  let zones = content.zones.map((z) => ({ ...z, memberNodeIds: [...(z.memberNodeIds ?? [])] }));
  let relationships = [...content.relationships];

  if (op.type === 'add-entity') {
    nodes = [
      ...nodes,
      {
        nodeId: newId('pnode_'),
        name: op.name?.trim() || 'Physical entity',
        nodeType: op.nodeType ?? 'module',
        electricalNodeIds: [],
        placementStatus: 'unresolved',
        qualitativePlacement: op.qualitativePlacement ?? 'Placement unresolved.',
        constraints: [],
        provenance: { schemaVersion: '1.0.0', sourceType: 'user' },
      },
    ];
  } else if (op.type === 'delete-entity') {
    nodes = nodes.filter((n) => n.nodeId !== op.nodeId);
    relationships = relationships.filter(
      (r) => r.fromNodeId !== op.nodeId && r.toNodeId !== op.nodeId,
    );
    zones = zones.map((zone) => ({
      ...zone,
      memberNodeIds: (zone.memberNodeIds ?? []).filter((id) => id !== op.nodeId),
    }));
  } else if (op.type === 'add-zone') {
    zones = [
      ...zones,
      {
        zoneId: newId('pzone_'),
        name: op.name?.trim() || 'Zone',
        zoneKind: op.zoneKind ?? 'other',
        memberNodeIds: [],
        notes: 'User-authored zone.',
      },
    ];
  } else if (op.type === 'assign-zone') {
    nodes = nodes.map((node) =>
      node.nodeId === op.nodeId
        ? {
            ...node,
            zoneId: op.zoneId,
            placementStatus: 'provisional' as const,
            qualitativePlacement:
              op.qualitativePlacement ?? `Assigned to zone ${op.zoneId}.`,
            provenance: { schemaVersion: '1.0.0' as const, sourceType: 'user' as const },
          }
        : node,
    );
    zones = zones.map((zone) => {
      const members = (zone.memberNodeIds ?? []).filter((id) => id !== op.nodeId);
      if (zone.zoneId === op.zoneId) members.push(op.nodeId);
      return { ...zone, memberNodeIds: members };
    });
  } else if (op.type === 'add-relationship') {
    relationships = [
      ...relationships,
      {
        relationshipId: newId('prel_'),
        fromNodeId: op.fromNodeId,
        toNodeId: op.toNodeId,
        relationshipType: op.relationshipType ?? 'adjacent-to',
        status: 'provisional',
        provenance: { schemaVersion: '1.0.0', sourceType: 'user' },
      },
    ];
  } else if (op.type === 'delete-relationship') {
    relationships = relationships.filter((r) => r.relationshipId !== op.relationshipId);
  } else if (op.type === 'delete-zone') {
    zones = zones.filter((z) => z.zoneId !== op.zoneId);
    nodes = nodes.map((node) =>
      node.zoneId === op.zoneId
        ? {
            ...node,
            zoneId: undefined,
            placementStatus: 'unresolved' as const,
            qualitativePlacement: 'Zone removed; placement unresolved.',
            provenance: { schemaVersion: '1.0.0' as const, sourceType: 'user' as const },
          }
        : node,
    );
  } else if (op.type === 'change-relationship') {
    relationships = relationships.map((rel) => {
      if (rel.relationshipId !== op.relationshipId) return rel;
      return {
        ...rel,
        ...(op.relationshipType != null ? { relationshipType: op.relationshipType } : {}),
        ...(op.status != null ? { status: op.status } : {}),
        provenance: { schemaVersion: '1.0.0' as const, sourceType: 'user' as const },
      };
    });
  } else if (op.type === 'edit-placement') {
    nodes = nodes.map((node) => {
      if (node.nodeId !== op.nodeId) return node;
      return {
        ...node,
        ...(op.qualitativePlacement != null
          ? { qualitativePlacement: op.qualitativePlacement }
          : {}),
        ...(op.placementStatus != null ? { placementStatus: op.placementStatus } : {}),
        provenance: { schemaVersion: '1.0.0' as const, sourceType: 'user' as const },
      };
    });
  }

  return {
    ...content,
    nodes,
    zones,
    relationships,
    coverageSummary: {
      ...content.coverageSummary,
      unresolvedPlacementCount: nodes.filter((n) =>
        ['unresolved', 'unknown'].includes(n.placementStatus),
      ).length,
      provisionalRelationshipCount: relationships.filter((r) => r.status === 'provisional')
        .length,
    },
  };
}

export function ArchitectureWorkspace({
  projectId,
  viewId,
  artifact,
  componentPlan,
  isDark,
  selectedNodeId = null,
  onSelectNode,
  onChangeView,
  electricalMode = 'design',
  onChangeElectricalMode,
  onAskVera,
  onCommandResult,
  onProjectStateRefresh,
  onSemanticPatch,
}: Props) {
  const t = themeColors(isDark);
  const viewMeta = ARCHITECTURE_VIEW_REGISTRY[viewId];
  const artifactType = artifactTypeFromView(viewId);

  const [draftContent, setDraftContent] = useState<ArchitectureDraftContent | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceDescriptor | null>(null);
  const [draftVersion, setDraftVersion] = useState(0);
  const [commandBusy, setCommandBusy] = useState(false);
  const [commandMessage, setCommandMessage] = useState<string | null>(null);
  const [layoutPositions, setLayoutPositions] = useState<GraphLayoutPositions>({});
  const [layoutViewport, setLayoutViewport] = useState<GraphLayoutViewport | undefined>();
  const [leaseToken, setLeaseToken] = useState<string | null>(null);
  const [leaseBlocked, setLeaseBlocked] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [historyTick, setHistoryTick] = useState(0);
  const [draftForm, setDraftForm] = useState<DraftFormState | null>(null);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(null);
  const [ensureBusy, setEnsureBusy] = useState(false);
  const [ensureMessage, setEnsureMessage] = useState<string | null>(null);

  const historyRef = useRef(new EditSessionHistory<ArchitectureDraftContent>());
  const leaseTokenRef = useRef<string | null>(null);
  const workspaceRef = useRef<WorkspaceDescriptor | null>(null);
  const artifactRef = useRef<ArchitectureArtifact | undefined>(artifact);

  useEffect(() => {
    leaseTokenRef.current = leaseToken;
  }, [leaseToken]);
  useEffect(() => {
    workspaceRef.current = workspace;
  }, [workspace]);
  useEffect(() => {
    artifactRef.current = artifact;
  }, [artifact]);

  const artifactIdentity = artifact
    ? `${artifact.artifactType}:${artifact.artifactId}:v${artifact.artifactVersion}`
    : null;

  useEffect(() => {
    if (!artifact || !artifactIdentity) {
      setDraftContent(null);
      setDirty(false);
      historyRef.current = new EditSessionHistory<ArchitectureDraftContent>();
      setHistoryTick((n) => n + 1);
      return;
    }
    setDraftContent(artifact.content);
    historyRef.current.reset(artifact.content, 'baseline');
    setDirty(false);
    setHistoryTick((n) => n + 1);
    // Reset draft/history only when accepted artifact identity/version changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional identity key
  }, [artifactIdentity]);

  useEffect(() => {
    if (!artifact) {
      setLayoutPositions({});
      setLayoutViewport(undefined);
      return;
    }
    // artifactId is part of layout identity; entity positions survive via sibling migration.
    const saved = loadArchitectureLayout(projectId, artifact.artifactType, artifact.artifactId);
    setLayoutPositions(saved?.positions ?? {});
    setLayoutViewport(saved?.viewport);
  }, [artifact?.artifactId, artifact?.artifactType, projectId]);

  // Release lease on unmount when we hold one.
  useEffect(() => {
    return () => {
      const token = leaseTokenRef.current;
      const ws = workspaceRef.current;
      const art = artifactRef.current;
      if (!token || !ws || !art) return;
      void submitArtifactCommand(projectId, {
        schemaVersion: '1.0.0',
        commandId: newCommandId(),
        commandType: 'workspace.release-edit-lease',
        projectId,
        artifactId: art.artifactId,
        workspaceId: ws.workspaceId,
        baseArtifactVersion: art.artifactVersion,
        baseProjectStateVersion: ws.baseProjectStateVersion,
        requestedAt: new Date().toISOString(),
        requestedBy: userActor(),
        input: { leaseToken: token },
      }).catch(() => {
        /* best-effort release */
      });
    };
  }, [projectId]);

  const refreshWorkspace = useCallback(async () => {
    try {
      const raw = await getWorkspace(projectId, artifactType);
      const envelope = unwrapWorkspace(raw);
      if (envelope) {
        setWorkspace(envelope.workspace);
        if (envelope.draft) {
          setDraftVersion(envelope.draft.draftVersion);
          if (envelope.draft.content && typeof envelope.draft.content === 'object') {
            const incoming = envelope.draft.content as ArchitectureDraftContent;
            const matches =
              (artifactType === 'functional-architecture' &&
                isFunctionalDraftContent(incoming)) ||
              (artifactType === 'electrical-architecture' &&
                isElectricalDraftContent(incoming)) ||
              (artifactType === 'physical-architecture' && isPhysicalDraftContent(incoming));
            if (matches) setDraftContent(incoming);
          }
          const held = envelope.draft.editLease;
          if (held && held.ownerActorId !== 'user_local' && held.leaseToken !== leaseTokenRef.current) {
            setLeaseBlocked(true);
          }
        }
      }
    } catch (err) {
      if (err instanceof ApiClientError && (err.status === 404 || err.status === 501)) {
        setWorkspace(null);
        return;
      }
      setCommandMessage(
        err instanceof ApiClientError ? err.message : 'Failed to load architecture workspace',
      );
    }
  }, [artifactType, projectId]);

  useEffect(() => {
    void refreshWorkspace();
  }, [refreshWorkspace]);

  useEffect(() => {
    setDraftForm(null);
    setConfirmDialog(null);
  }, [viewId, artifactIdentity]);

  const graph = useMemo(() => {
    if (!artifact) return { nodes: [], edges: [] };
    let dto;
    if (artifact.artifactType === 'functional-architecture') {
      const content = isFunctionalDraftContent(draftContent)
        ? draftContent
        : artifact.content;
      dto = adaptFunctionalArchitecture(content);
    } else if (artifact.artifactType === 'electrical-architecture') {
      const content = isElectricalDraftContent(draftContent)
        ? draftContent
        : artifact.content;
      dto = adaptElectricalArchitecture(content);
    } else {
      const content = isPhysicalDraftContent(draftContent)
        ? draftContent
        : artifact.content;
      dto = adaptPhysicalArchitecture(content);
    }
    return {
      nodes: applyLayoutPositions(dto.nodes, layoutPositions),
      edges: dto.edges,
    };
  }, [artifact, draftContent, layoutPositions]);

  const electricalVisualGraph = useMemo(() => {
    if (viewId !== 'electrical' || !artifact || artifact.artifactType !== 'electrical-architecture') {
      return null;
    }
    const content = isElectricalDraftContent(draftContent) ? draftContent : artifact.content;
    const candidatesById: Record<
      string,
      {
        candidateId: string;
        partNumber?: string;
        manufacturer?: string;
        displayName?: string;
        category?: string;
      }
    > = {};
    const roleCategoryById: Record<string, string> = {};
    if (componentPlan) {
      for (const role of componentPlan.content.componentRoles) {
        roleCategoryById[role.componentRoleId] = role.category;
      }
      for (const candidate of componentPlan.content.candidates) {
        candidatesById[candidate.candidateId] = {
          candidateId: candidate.candidateId,
          partNumber: candidate.partNumber,
          manufacturer: candidate.manufacturer,
          displayName: candidate.displayName,
          category: candidate.candidateCategory,
        };
      }
    }
    const adapted = adaptElectricalVisualGraph(content, { candidatesById, roleCategoryById });
    return {
      nodes: adapted.nodes.map((node) => ({
        ...node,
        position: layoutPositions[node.id] ?? node.position,
      })),
      edges: adapted.edges,
      powerRails: adapted.powerRails,
    };
  }, [artifact, componentPlan, draftContent, layoutPositions, viewId]);

  const electricalValidationCounts = useMemo(() => {
    if (!artifact || artifact.artifactType !== 'electrical-architecture') {
      return { blocking: 0, warnings: 0, passed: 0 };
    }
    const content = isElectricalDraftContent(draftContent) ? draftContent : artifact.content;
    const findings = content.warnings ?? [];
    return {
      blocking: findings.filter((item) => item.severity === 'blocking').length,
      warnings: findings.filter((item) => item.severity === 'warning').length,
      passed: findings.filter((item) => item.severity === 'info').length,
    };
  }, [artifact, draftContent]);

  const selectedDto = graph.nodes.find((n) => n.id === selectedNodeId) ?? graph.nodes[0];

  const handleLayoutDragStop = useCallback(
    (positions: GraphLayoutPositions) => {
      if (!artifact) return;
      setLayoutPositions(positions);
      // Layout save only — never propose/accept or submitArtifactCommand for semantic revision.
      saveArchitectureLayout({
        projectId,
        artifactType: artifact.artifactType,
        artifactId: artifact.artifactId,
        positions,
        viewport: layoutViewport,
        activeEntityIds: graph.nodes.map((n) => n.id),
      });
    },
    [artifact, graph.nodes, layoutViewport, projectId],
  );

  function handleResetLayout(): void {
    if (!artifact) return;
    resetArchitectureLayout(projectId, artifact.artifactType, artifact.artifactId);
    setLayoutPositions({});
    setLayoutViewport(undefined);
    setCommandMessage('Layout reset');
  }

  async function ensureWorkspace(): Promise<WorkspaceEnvelope | null> {
    if (workspace) {
      return {
        workspace,
        draft: draftVersion ? ({ draftVersion } as WorkspaceDraftState) : undefined,
      };
    }
    try {
      const raw = await createWorkspace(projectId, artifactType);
      const envelope = unwrapWorkspace(raw);
      if (!envelope) {
        setCommandMessage('Unexpected workspace response shape.');
        return null;
      }
      setWorkspace(envelope.workspace);
      if (envelope.draft) setDraftVersion(envelope.draft.draftVersion);
      return envelope;
    } catch (err) {
      if (err instanceof ApiClientError && (err.status === 404 || err.status === 501)) {
        setCommandMessage('Workspace API is not available yet.');
        return null;
      }
      setCommandMessage(err instanceof ApiClientError ? err.message : 'Failed to create workspace');
      return null;
    }
  }

  async function ensureEditLease(): Promise<boolean> {
    if (leaseBlocked) return false;
    if (leaseToken) return true;
    if (!artifact) return false;

    const envelope = await ensureWorkspace();
    if (!envelope) return false;

    try {
      const result = await submitArtifactCommand(projectId, {
        schemaVersion: '1.0.0',
        commandId: newCommandId(),
        commandType: 'workspace.acquire-edit-lease',
        projectId,
        artifactId: artifact.artifactId,
        workspaceId: envelope.workspace.workspaceId,
        baseArtifactVersion: artifact.artifactVersion,
        baseProjectStateVersion: envelope.workspace.baseProjectStateVersion,
        requestedAt: new Date().toISOString(),
        requestedBy: userActor(),
        input: {},
      });
      onCommandResult?.(result);
      if (isLeaseHeldResult(result)) {
        setLeaseBlocked(true);
        setCommandMessage('Another editor holds the draft lease');
        return false;
      }
      if (result.status === 'failed' || result.status === 'rejected') {
        setCommandMessage(result.error?.message ?? `Lease acquire ${result.status}`);
        return false;
      }
      const token =
        (result.resultPayload?.editLease as { leaseToken?: string } | undefined)?.leaseToken ??
        null;
      if (token) {
        setLeaseToken(token);
        leaseTokenRef.current = token;
      }
      setLeaseBlocked(false);
      return true;
    } catch (err) {
      if (isLeaseHeldError(err)) {
        setLeaseBlocked(true);
        setCommandMessage('Another editor holds the draft lease');
        return false;
      }
      if (err instanceof ApiClientError && (err.status === 404 || err.status === 501)) {
        // Local-only editing when lease API is unavailable.
        return true;
      }
      setCommandMessage(err instanceof ApiClientError ? err.message : 'Failed to acquire edit lease');
      return false;
    }
  }

  async function releaseLease(): Promise<void> {
    const token = leaseTokenRef.current;
    if (!token || !artifact || !workspace) return;
    try {
      await submitArtifactCommand(projectId, {
        schemaVersion: '1.0.0',
        commandId: newCommandId(),
        commandType: 'workspace.release-edit-lease',
        projectId,
        artifactId: artifact.artifactId,
        workspaceId: workspace.workspaceId,
        baseArtifactVersion: artifact.artifactVersion,
        baseProjectStateVersion: workspace.baseProjectStateVersion,
        requestedAt: new Date().toISOString(),
        requestedBy: userActor(),
        input: { leaseToken: token },
      });
    } catch {
      /* best-effort */
    } finally {
      setLeaseToken(null);
      leaseTokenRef.current = null;
    }
  }

  async function runCommand(build: (ws: WorkspaceDescriptor) => ArtifactCommand): Promise<void> {
    if (!artifact || commandBusy) return;
    setCommandBusy(true);
    setCommandMessage(null);
    try {
      const envelope = await ensureWorkspace();
      if (!envelope) return;
      const result = await submitArtifactCommand(projectId, build(envelope.workspace));
      onCommandResult?.(result);
      setCommandMessage(`Command ${result.commandId}: ${result.status}`);
      await refreshWorkspace();
    } catch (err) {
      if (err instanceof ApiClientError && (err.status === 404 || err.status === 501)) {
        setCommandMessage('Artifact command API is not available yet.');
      } else {
        setCommandMessage(err instanceof ApiClientError ? err.message : 'Command failed');
      }
    } finally {
      setCommandBusy(false);
    }
  }

  async function runCircuitSimulation(): Promise<void> {
    if (!artifact || artifact.artifactType !== 'electrical-architecture') {
      throw new Error('Circuit simulation requires an electrical architecture.');
    }
    if (commandBusy) throw new Error('Another architecture command is running.');
    const leased = await ensureEditLease();
    if (!leased) throw new Error('An active edit lease is required to snapshot simulation input.');
    setCommandBusy(true);
    setCommandMessage(null);
    try {
      const envelope = await ensureWorkspace();
      if (!envelope) throw new Error('Unable to create the electrical architecture workspace.');
      const ws = envelope.workspace;
      const snapshotResult = await submitArtifactCommand(projectId, {
        schemaVersion: '1.0.0',
        commandId: newCommandId(),
        commandType: 'workspace.create-snapshot',
        projectId,
        artifactId: artifact.artifactId,
        workspaceId: ws.workspaceId,
        baseArtifactVersion: artifact.artifactVersion,
        baseProjectStateVersion: ws.baseProjectStateVersion,
        requestedAt: new Date().toISOString(),
        requestedBy: userActor(),
        input: { reason: 'Circuit simulation input snapshot' },
      });
      onCommandResult?.(snapshotResult);
      if (snapshotResult.status === 'failed' || snapshotResult.status === 'rejected') {
        throw new Error(snapshotResult.error?.message ?? 'Workspace snapshot failed.');
      }

      let snapshotId =
        snapshotResult.snapshotId ??
        (snapshotResult.resultPayload?.snapshotId as string | undefined);
      let executionWorkspace = ws;
      if (!snapshotId) {
        const current = unwrapWorkspace(await getWorkspace(projectId, artifact.artifactType));
        if (current) {
          executionWorkspace = current.workspace;
          snapshotId = current.workspace.currentSnapshotId;
          setWorkspace(current.workspace);
        }
      }
      if (!snapshotId) throw new Error('Snapshot command did not return a snapshot identifier.');

      const executionResult = await submitArtifactCommand(projectId, {
        schemaVersion: '1.0.0',
        commandId: newCommandId(),
        commandType: 'artifact.execute',
        projectId,
        artifactId: artifact.artifactId,
        workspaceId: executionWorkspace.workspaceId,
        baseArtifactVersion: artifact.artifactVersion,
        baseProjectStateVersion: executionWorkspace.baseProjectStateVersion,
        requestedAt: new Date().toISOString(),
        requestedBy: userActor(),
        input: {
          snapshotId,
          capability: 'circuit-simulation',
          executionMode: 'simulate',
          expectedText: 'NEXUS_WOKWI_READY',
          requestedOutputs: ['serial-log', 'provider-workspace'],
          maxDurationMs: 30_000,
          maxOutputBytes: 1_048_576,
        },
      });
      onCommandResult?.(executionResult);
      if (executionResult.status === 'failed' || executionResult.status === 'rejected') {
        throw new Error(executionResult.error?.message ?? 'Circuit simulation failed.');
      }
      setCommandMessage(`Simulation command ${executionResult.commandId}: ${executionResult.status}`);
      await refreshWorkspace();
    } finally {
      setCommandBusy(false);
    }
  }

  async function persistDraftContent(
    next: ArchitectureDraftContent,
    options?: { recordHistory?: boolean; label?: string },
  ): Promise<boolean> {
    if (!artifact) return false;

    const leased = await ensureEditLease();
    if (!leased) return false;

    if (options?.recordHistory !== false) {
      historyRef.current.push(next, options?.label ?? 'edit');
      setHistoryTick((n) => n + 1);
    }

    setDraftContent(next);
    setDirty(true);
    if (
      viewId === 'system' &&
      artifact.artifactType === 'functional-architecture'
    ) {
      onSemanticPatch?.(() => next as FunctionalArchitectureContent);
    }

    const envelope = await ensureWorkspace();
    if (!envelope) return true;

    const expected = envelope.draft?.draftVersion ?? draftVersion;
    setCommandBusy(true);
    setCommandMessage(null);
    try {
      const result = await submitArtifactCommand(projectId, {
        schemaVersion: '1.0.0',
        commandId: newCommandId(),
        commandType: 'workspace.update-draft',
        projectId,
        artifactId: artifact.artifactId,
        workspaceId: envelope.workspace.workspaceId,
        baseArtifactVersion: artifact.artifactVersion,
        baseProjectStateVersion: envelope.workspace.baseProjectStateVersion,
        requestedAt: new Date().toISOString(),
        requestedBy: userActor(),
        input: {
          content: next as unknown as Record<string, unknown>,
          expectedDraftVersion: expected,
        },
      });
      onCommandResult?.(result);
      if (isLeaseHeldResult(result)) {
        setLeaseBlocked(true);
        setCommandMessage('Another editor holds the draft lease');
        return false;
      }
      setDraftVersion(expected + 1);
      setCommandMessage(`Draft updated (${result.status})`);
      await refreshWorkspace();
      return true;
    } catch (err) {
      if (isLeaseHeldError(err)) {
        setLeaseBlocked(true);
        setCommandMessage('Another editor holds the draft lease');
        return false;
      }
      if (err instanceof ApiClientError && (err.status === 404 || err.status === 501)) {
        setCommandMessage('Draft saved locally. Artifact command API is not available yet.');
        return true;
      }
      setCommandMessage(err instanceof ApiClientError ? err.message : 'Failed to update draft');
      return false;
    } finally {
      setCommandBusy(false);
    }
  }

  function runElectricalSemanticOp(op: ElectricalSemanticOp): void {
    if (viewId !== 'electrical' || !isElectricalDraftContent(draftContent)) return;
    try {
      const next = applyElectricalSemanticOp(draftContent, op);
      void persistDraftContent(next, { label: op.type });
      if (op.type === 'add-supporting-node') {
        const added = next.nodes[next.nodes.length - 1];
        if (added) onSelectNode?.(added.nodeId);
      }
      if (op.type === 'delete-supporting-node' && selectedNodeId === op.nodeId) {
        onSelectNode?.(next.nodes[0]?.nodeId ?? null);
      }
    } catch (err) {
      setConfirmDialog({
        title: 'Cannot apply edit',
        summary: err instanceof Error ? err.message : String(err),
        destructive: false,
      });
    }
  }

  function runPhysicalSemanticOp(op: PhysicalSemanticOp): void {
    if (viewId !== 'physical' || !isPhysicalDraftContent(draftContent)) return;
    const next = applyPhysicalSemanticOp(draftContent, op);
    void persistDraftContent(next, { label: op.type });
    if (op.type === 'add-entity') {
      const added = next.nodes[next.nodes.length - 1];
      if (added) onSelectNode?.(added.nodeId);
    }
    if (op.type === 'delete-entity' && selectedNodeId === op.nodeId) {
      onSelectNode?.(next.nodes[0]?.nodeId ?? null);
    }
  }

  function runSystemSemanticOp(op: ArchitectureSemanticOp): void {
    if (viewId !== 'system' || !isFunctionalDraftContent(draftContent)) return;
    const next = recomputeCoverage(applySemanticOp(draftContent, op));
    void persistDraftContent(next, { label: op.type });
    if (op.type === 'add-node') {
      const added = next.nodes[next.nodes.length - 1];
      if (added) onSelectNode?.(added.nodeId);
    }
    if (
      (op.type === 'delete-node' || op.type === 'remove-and-reconcile') &&
      selectedNodeId === op.nodeId
    ) {
      onSelectNode?.(next.nodes[0]?.nodeId ?? null);
    }
  }

  async function handleDeleteFunctionalNode(nodeId: string, label: string): Promise<void> {
    if (!artifact || !isFunctionalDraftContent(draftContent)) return;
    setCommandMessage(null);
    try {
      const envelope = await ensureWorkspace();
      if (!envelope) return;
      const result = await submitArtifactCommand(projectId, {
        schemaVersion: '1.0.0',
        commandId: newCommandId(),
        commandType: 'artifact.inspect-deletion-impact',
        projectId,
        artifactId: artifact.artifactId,
        workspaceId: envelope.workspace.workspaceId,
        baseArtifactVersion: artifact.artifactVersion,
        baseProjectStateVersion: envelope.workspace.baseProjectStateVersion,
        requestedAt: new Date().toISOString(),
        requestedBy: userActor(),
        input: { entityType: 'functional-node', entityId: nodeId },
      });
      onCommandResult?.(result);
      const impact = (result.resultPayload ?? {}) as DeletionImpactPayload;
      const roleCount = impact.affectedComponentRoleIds?.length ?? 0;
      const electricalCount = impact.affectedElectricalNodeIds?.length ?? 0;
      if (impact.blocking || roleCount > 0 || electricalCount > 0) {
        const summary =
          impact.summary ??
          `Deleting “${label}” may affect downstream component roles or electrical nodes.`;
        setConfirmDialog({
          title: 'Confirm remove-and-reconcile',
          summary: `${summary}\n\nDownstream layers reconcile on accept.`,
          confirmLabel: 'Remove and reconcile',
          destructive: true,
          onConfirm: () => runSystemSemanticOp({ type: 'remove-and-reconcile', nodeId }),
        });
        return;
      }
      setConfirmDialog({
        title: 'Delete node',
        summary: `Delete node “${label}”?`,
        confirmLabel: 'Delete',
        destructive: true,
        onConfirm: () => runSystemSemanticOp({ type: 'delete-node', nodeId }),
      });
    } catch (err) {
      if (err instanceof ApiClientError && (err.status === 404 || err.status === 501)) {
        setConfirmDialog({
          title: 'Delete node',
          summary: `Delete node “${label}”?`,
          confirmLabel: 'Delete',
          destructive: true,
          onConfirm: () => runSystemSemanticOp({ type: 'delete-node', nodeId }),
        });
        return;
      }
      setCommandMessage(
        err instanceof ApiClientError ? err.message : 'Failed to inspect deletion impact',
      );
    }
  }

  async function handleEnsureLayeredArchitecture(): Promise<void> {
    setEnsureBusy(true);
    setEnsureMessage(null);
    try {
      await ensureLayeredArchitecture(projectId);
      onProjectStateRefresh?.();
    } catch (err) {
      setEnsureMessage(
        err instanceof ApiClientError ? err.message : 'Failed to generate layered architecture',
      );
    } finally {
      setEnsureBusy(false);
    }
  }

  function submitDraftForm(): void {
    if (!draftForm) return;
    const form = draftForm;
    setDraftForm(null);
    switch (form.kind) {
      case 'add-node':
        runSystemSemanticOp({
          type: 'add-node',
          name: form.name,
          functionalType: form.functionalType,
        });
        break;
      case 'rename-node':
        if (!form.name.trim()) return;
        runSystemSemanticOp({
          type: 'rename-node',
          nodeId: form.nodeId,
          name: form.name.trim(),
        });
        break;
      case 'add-edge':
        runSystemSemanticOp({
          type: 'add-edge',
          fromNodeId: form.fromNodeId,
          toNodeId: form.toNodeId,
          flowType: form.flowType,
        });
        break;
      case 'change-edge-flow':
        runSystemSemanticOp({
          type: 'change-edge-flow',
          edgeId: form.edgeId,
          flowType: form.flowType,
        });
        break;
      case 'delete-edge':
        setConfirmDialog({
          title: 'Delete edge',
          summary: `Delete edge “${form.edgeId}”?`,
          confirmLabel: 'Delete',
          destructive: true,
          onConfirm: () => runSystemSemanticOp({ type: 'delete-edge', edgeId: form.edgeId }),
        });
        break;
      case 'add-supporting-node':
        runElectricalSemanticOp({ type: 'add-supporting-node', name: form.name });
        break;
      case 'add-connection':
        runElectricalSemanticOp({
          type: 'add-connection',
          fromNodeId: form.fromNodeId,
          toNodeId: form.toNodeId,
          connectionType: form.connectionType,
          interfaceType: form.interfaceType,
        });
        break;
      case 'delete-connection':
        setConfirmDialog({
          title: 'Delete connection',
          summary: `Delete connection “${form.connectionId}”?`,
          confirmLabel: 'Delete',
          destructive: true,
          onConfirm: () =>
            runElectricalSemanticOp({
              type: 'delete-connection',
              connectionId: form.connectionId,
            }),
        });
        break;
      case 'change-connection-type':
        runElectricalSemanticOp({
          type: 'change-connection',
          connectionId: form.connectionId,
          connectionType: form.connectionType,
        });
        break;
      case 'change-interface-type':
        runElectricalSemanticOp({
          type: 'change-connection',
          connectionId: form.connectionId,
          interfaceType: form.interfaceType,
        });
        break;
      case 'mark-connection-status':
        runElectricalSemanticOp({
          type: 'mark-connection-status',
          connectionId: form.connectionId,
          status: form.status,
        });
        break;
      case 'add-entity':
        runPhysicalSemanticOp({
          type: 'add-entity',
          name: form.name,
          nodeType: form.nodeType,
        });
        break;
      case 'add-zone':
        runPhysicalSemanticOp({
          type: 'add-zone',
          name: form.name,
          zoneKind: form.zoneKind,
        });
        break;
      case 'delete-zone':
        setConfirmDialog({
          title: 'Delete zone',
          summary: `Delete zone “${form.zoneId}”?`,
          confirmLabel: 'Delete',
          destructive: true,
          onConfirm: () => runPhysicalSemanticOp({ type: 'delete-zone', zoneId: form.zoneId }),
        });
        break;
      case 'assign-zone':
        runPhysicalSemanticOp({
          type: 'assign-zone',
          nodeId: form.nodeId,
          zoneId: form.zoneId,
        });
        break;
      case 'add-relationship':
        runPhysicalSemanticOp({
          type: 'add-relationship',
          fromNodeId: form.fromNodeId,
          toNodeId: form.toNodeId,
          relationshipType: form.relationshipType,
        });
        break;
      case 'change-relationship':
        runPhysicalSemanticOp({
          type: 'change-relationship',
          relationshipId: form.relationshipId,
          relationshipType: form.relationshipType,
        });
        break;
      case 'delete-relationship':
        setConfirmDialog({
          title: 'Delete relationship',
          summary: `Delete relationship “${form.relationshipId}”?`,
          confirmLabel: 'Delete',
          destructive: true,
          onConfirm: () =>
            runPhysicalSemanticOp({
              type: 'delete-relationship',
              relationshipId: form.relationshipId,
            }),
        });
        break;
      case 'edit-placement':
        runPhysicalSemanticOp({
          type: 'edit-placement',
          nodeId: form.nodeId,
          qualitativePlacement: form.qualitativePlacement,
          placementStatus: form.placementStatus,
        });
        break;
      default:
        break;
    }
  }

  async function handleUndo(): Promise<void> {
    const prev = historyRef.current.undo();
    setHistoryTick((n) => n + 1);
    if (!prev) return;
    await persistDraftContent(prev, { recordHistory: false });
  }

  async function handleRedo(): Promise<void> {
    const next = historyRef.current.redo();
    setHistoryTick((n) => n + 1);
    if (!next) return;
    await persistDraftContent(next, { recordHistory: false });
  }

  async function handleDiscard(): Promise<void> {
    if (!artifact) return;
    const leased = await ensureEditLease();
    if (!leased && leaseBlocked) return;

    setCommandBusy(true);
    setCommandMessage(null);
    try {
      const envelope = await ensureWorkspace();
      if (envelope) {
        const result = await submitArtifactCommand(projectId, {
          schemaVersion: '1.0.0',
          commandId: newCommandId(),
          commandType: 'workspace.discard-draft',
          projectId,
          artifactId: artifact.artifactId,
          workspaceId: envelope.workspace.workspaceId,
          baseArtifactVersion: artifact.artifactVersion,
          baseProjectStateVersion: envelope.workspace.baseProjectStateVersion,
          requestedAt: new Date().toISOString(),
          requestedBy: userActor(),
          input: {
            expectedDraftVersion: envelope.draft?.draftVersion ?? draftVersion,
          },
        });
        onCommandResult?.(result);
        setCommandMessage(`Draft discarded (${result.status})`);
      }
      setDraftContent(artifact.content);
      historyRef.current.reset(artifact.content, 'baseline');
      setHistoryTick((n) => n + 1);
      setDirty(false);
      await releaseLease();
      await refreshWorkspace();
    } catch (err) {
      if (err instanceof ApiClientError && (err.status === 404 || err.status === 501)) {
        setDraftContent(artifact.content);
        historyRef.current.reset(artifact.content, 'baseline');
        setHistoryTick((n) => n + 1);
        setDirty(false);
        setCommandMessage('Draft discarded locally.');
        return;
      }
      setCommandMessage(err instanceof ApiClientError ? err.message : 'Failed to discard draft');
    } finally {
      setCommandBusy(false);
    }
  }

  // historyTick forces re-render when undo/redo stack changes (history lives in a ref).
  const canUndo = historyTick >= 0 && historyRef.current.canUndo();
  const canRedo = historyTick >= 0 && historyRef.current.canRedo();
  const semanticDisabled = commandBusy || leaseBlocked;

  const summaryLine = useMemo(() => {
    if (!artifact) return 'No architecture artifact loaded';
    try {
      if (artifact.artifactType === 'functional-architecture') {
        const content = isFunctionalDraftContent(draftContent)
          ? draftContent
          : artifact.content;
        const boundary = String(content.systemBoundary ?? '');
        const covered = content.requirementCoverage?.coveredRequirementIds?.length ?? 0;
        return `${content.architectureMaturity ?? 'unknown'} · ${boundary.slice(0, 80)}${
          boundary.length > 80 ? '…' : ''
        } · Coverage: ${covered}`;
      }
      if (artifact.artifactType === 'electrical-architecture') {
        const c = isElectricalDraftContent(draftContent) ? draftContent : artifact.content;
        const covered = c.coverageSummary?.coveredFunctionalNodes ?? 0;
        const total = c.coverageSummary?.totalFunctionalNodes ?? 0;
        const connections = Array.isArray(c.connections) ? c.connections.length : 0;
        return `${c.maturity ?? 'unknown'} · ${covered}/${total} functional nodes · ${connections} connections`;
      }
      const c = isPhysicalDraftContent(draftContent) ? draftContent : artifact.content;
      const covered = c.coverageSummary?.coveredElectricalNodes ?? 0;
      const total = c.coverageSummary?.totalElectricalNodes ?? 0;
      const relationships = Array.isArray(c.relationships) ? c.relationships.length : 0;
      return `${c.maturity ?? 'unknown'} · ${covered}/${total} electrical nodes · ${relationships} relationships`;
    } catch {
      return 'Architecture summary unavailable';
    }
  }, [artifact, draftContent]);

  const btnStyle = (active: boolean): CSSProperties => ({
    fontSize: 12,
    fontWeight: active ? 600 : 500,
    color: active ? t.cobalt : t.textMuted,
    background: active ? t.cobaltSelected : 'transparent',
    padding: '4px 10px',
    borderRadius: 6,
    border: active ? `1px solid ${t.cobalt}` : '1px solid transparent',
    cursor: 'pointer',
  });

  const toolBtn: CSSProperties = {
    fontSize: 12,
    padding: '4px 10px',
    borderRadius: 6,
    border: `1px solid ${t.border}`,
    background: t.surface,
    color: t.text,
    cursor: commandBusy || leaseBlocked ? 'not-allowed' : 'pointer',
    opacity: commandBusy || leaseBlocked ? 0.6 : 1,
  };

  const systemDraft = isFunctionalDraftContent(draftContent) ? draftContent : null;
  const electricalDraft = isElectricalDraftContent(draftContent) ? draftContent : null;
  const physicalDraft = isPhysicalDraftContent(draftContent) ? draftContent : null;

  if (!artifact) {
    const showEnsure =
      viewId === 'electrical' || viewId === 'physical';
    return (
      <div
        style={{ flex: 1, overflow: 'auto', padding: 24, background: t.bg }}
        data-testid="workspace-architecture"
      >
        <div
          style={{
            maxWidth: 560,
            margin: '40px auto',
            padding: 20,
            borderRadius: 8,
            border: `1px dashed ${t.border}`,
            background: t.surface,
          }}
        >
          <h3 style={{ margin: 0, color: t.text }}>{viewMeta.label} architecture unavailable</h3>
          <p style={{ margin: '8px 0 0', fontSize: 13, color: t.textSec }}>
            No {viewMeta.artifactType} artifact is in the current project state yet.
          </p>
          {showEnsure ? (
            <div style={{ marginTop: 16, display: 'grid', gap: 8 }}>
              <button
                type="button"
                data-testid="architecture-ensure-layered"
                disabled={ensureBusy}
                style={{
                  ...toolBtn,
                  justifySelf: 'start',
                  opacity: ensureBusy ? 0.6 : 1,
                  cursor: ensureBusy ? 'not-allowed' : 'pointer',
                }}
                onClick={() => void handleEnsureLayeredArchitecture()}
              >
                {ensureBusy ? 'Generating…' : 'Generate layered architecture'}
              </button>
              {ensureMessage ? (
                <p role="status" style={{ margin: 0, fontSize: 12, color: t.textSec }}>
                  {ensureMessage}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
      data-testid="workspace-architecture"
    >
      <div
        style={{
          padding: '8px 16px',
          borderBottom: `1px solid ${t.border}`,
          background: t.surface,
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        {ARCHITECTURE_VIEW_ORDER.map((id) => (
          <button
            key={id}
            type="button"
            data-testid={`architecture-tab-${id}`}
            style={btnStyle(id === viewId)}
            onClick={() => onChangeView?.(id)}
          >
            {ARCHITECTURE_VIEW_REGISTRY[id].label}
          </button>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: 12, color: t.textSec }}>{summaryLine}</span>
        <button
          type="button"
          style={toolBtn}
          data-testid="architecture-reset-layout"
          disabled={commandBusy}
          onClick={handleResetLayout}
        >
          Reset layout
        </button>
        <button type="button" style={toolBtn} data-testid="architecture-ask-vera" onClick={() => onAskVera?.()}>
          Ask Vera
        </button>
      </div>

      {leaseBlocked ? (
        <div
          role="status"
          data-testid="architecture-lease-banner"
          style={{
            padding: '8px 16px',
            background: isDark ? '#3b2a1a' : '#fff7ed',
            borderBottom: `1px solid ${t.border}`,
            color: t.text,
            fontSize: 12,
          }}
        >
          Another editor holds the draft lease
        </div>
      ) : null}

      <div
        style={{
          padding: '6px 16px',
          borderBottom: `1px solid ${t.border}`,
          background: t.surface2,
          display: 'flex',
          gap: 8,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
        data-testid="architecture-session-toolbar"
      >
        <span style={{ fontSize: 11, color: t.textMuted, fontWeight: 600 }}>Session</span>
        <button
          type="button"
          style={toolBtn}
          disabled={semanticDisabled || !canUndo}
          data-testid="architecture-undo"
          onClick={() => void handleUndo()}
        >
          Undo
        </button>
        <button
          type="button"
          style={toolBtn}
          disabled={semanticDisabled || !canRedo}
          data-testid="architecture-redo"
          onClick={() => void handleRedo()}
        >
          Redo
        </button>
        <button
          type="button"
          style={toolBtn}
          disabled={semanticDisabled || !dirty}
          data-testid="architecture-discard"
          onClick={() => void handleDiscard()}
        >
          Discard
        </button>
        {commandMessage ? (
          <span role="status" style={{ fontSize: 11, color: t.textSec }}>
            {commandMessage}
          </span>
        ) : null}
      </div>

      {viewId === 'system' ? (
        <div
          style={{
            padding: '6px 16px',
            borderBottom: `1px solid ${t.border}`,
            background: t.surface2,
            display: 'flex',
            gap: 8,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
          data-testid="architecture-semantic-toolbar"
        >
          <span style={{ fontSize: 11, color: t.textMuted, fontWeight: 600 }}>Semantic edits</span>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled}
            data-testid="architecture-add-node"
            onClick={() =>
              setDraftForm({
                kind: 'add-node',
                name: 'New functional block',
                functionalType: 'processing',
              })
            }
          >
            Add node
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled || !selectedDto}
            data-testid="architecture-rename-node"
            onClick={() => {
              if (!selectedDto) return;
              setDraftForm({
                kind: 'rename-node',
                nodeId: selectedDto.id,
                name: selectedDto.label,
              });
            }}
          >
            Rename
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled || !selectedDto}
            data-testid="architecture-delete-node"
            onClick={() => {
              if (!selectedDto) return;
              void handleDeleteFunctionalNode(selectedDto.id, selectedDto.label);
            }}
          >
            Delete
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled || !selectedDto || (systemDraft?.nodes.length ?? 0) < 2}
            data-testid="architecture-add-edge"
            onClick={() => {
              if (!selectedDto || !systemDraft) return;
              const target =
                systemDraft.nodes.find((n) => n.nodeId !== selectedDto.id)?.nodeId ?? '';
              setDraftForm({
                kind: 'add-edge',
                fromNodeId: selectedDto.id,
                toNodeId: target,
                flowType: 'data',
              });
            }}
          >
            Add edge
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled || (systemDraft?.edges.length ?? 0) < 1}
            data-testid="architecture-change-edge-flow"
            onClick={() => {
              if (!systemDraft?.edges[0]) return;
              setDraftForm({
                kind: 'change-edge-flow',
                edgeId: systemDraft.edges[0].edgeId,
                flowType: systemDraft.edges[0].flowType,
              });
            }}
          >
            Change edge flow
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled || (systemDraft?.edges.length ?? 0) < 2}
            data-testid="architecture-delete-edge"
            onClick={() => {
              if (!systemDraft?.edges[0]) return;
              setDraftForm({
                kind: 'delete-edge',
                edgeId: systemDraft.edges[0].edgeId,
              });
            }}
          >
            Delete edge
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={commandBusy || !artifact}
            data-testid="architecture-create-snapshot"
            onClick={() =>
              void runCommand((ws) => ({
                schemaVersion: '1.0.0',
                commandId: newCommandId(),
                commandType: 'workspace.create-snapshot',
                projectId,
                artifactId: artifact.artifactId,
                workspaceId: ws.workspaceId,
                baseArtifactVersion: artifact.artifactVersion,
                baseProjectStateVersion: ws.baseProjectStateVersion,
                requestedAt: new Date().toISOString(),
                requestedBy: userActor(),
                input: { reason: 'Manual snapshot from architecture workspace' },
              }))
            }
          >
            Create snapshot
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={commandBusy || !artifact || !workspace?.currentSnapshotId}
            data-testid="architecture-propose-revision"
            onClick={() =>
              void runCommand((ws) => ({
                schemaVersion: '1.0.0',
                commandId: newCommandId(),
                commandType: 'artifact.propose-revision',
                projectId,
                artifactId: artifact.artifactId,
                workspaceId: ws.workspaceId,
                baseArtifactVersion: artifact.artifactVersion,
                baseProjectStateVersion: ws.baseProjectStateVersion,
                requestedAt: new Date().toISOString(),
                requestedBy: userActor(),
                input: {
                  snapshotId: ws.currentSnapshotId!,
                  consequenceLevel: 'medium',
                  summary: 'Propose functional-architecture revision from System view',
                },
              }))
            }
          >
            Propose revision
          </button>
        </div>
      ) : null}

      {viewId === 'electrical' ? (
        <div
          style={{
            padding: '6px 16px',
            borderBottom: `1px solid ${t.border}`,
            background: t.surface2,
            display: 'flex',
            gap: 8,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
          data-testid="architecture-electrical-toolbar"
        >
          <ElectricalModeTabs
            mode={electricalMode}
            isDark={isDark}
            onChange={(mode) => onChangeElectricalMode?.(mode)}
          />
          {electricalMode === 'design' ? (
            <>
              <span style={{ fontSize: 11, color: t.textMuted, fontWeight: 600 }}>Design</span>
              <button
                type="button"
                style={toolBtn}
                disabled={semanticDisabled}
                data-testid="architecture-add-supporting-node"
                onClick={() =>
                  setDraftForm({ kind: 'add-supporting-node', name: 'Supporting electronics' })
                }
              >
                Add
              </button>
              <button
                type="button"
                style={toolBtn}
                disabled={semanticDisabled || !selectedDto || (electricalDraft?.nodes.length ?? 0) < 2}
                data-testid="architecture-add-connection"
                onClick={() => {
                  if (!selectedDto || !electricalDraft) return;
                  const toNodeId =
                    electricalDraft.nodes.find((n) => n.nodeId !== selectedDto.id)?.nodeId ?? '';
                  setDraftForm({
                    kind: 'add-connection',
                    fromNodeId: selectedDto.id,
                    toNodeId,
                    connectionType: 'signal',
                    interfaceType: 'unknown',
                  });
                }}
              >
                Connect
              </button>
              <button
                type="button"
                style={toolBtn}
                disabled={semanticDisabled || !selectedDto}
                data-testid="architecture-delete-supporting-node"
                onClick={() => {
                  if (!selectedDto || !electricalDraft) return;
                  const node = electricalDraft.nodes.find((n) => n.nodeId === selectedDto.id);
                  if (!node) return;
                  if (node.componentRoleIds.length > 0) {
                    setConfirmDialog({
                      title: 'Cannot delete node',
                      summary:
                        'This node is bound to a Component Role. Change selection in Component Plan instead.',
                      destructive: false,
                    });
                    return;
                  }
                  setConfirmDialog({
                    title: 'Delete supporting node',
                    summary: `Delete supporting node “${selectedDto.label}”?`,
                    confirmLabel: 'Delete',
                    destructive: true,
                    onConfirm: () =>
                      runElectricalSemanticOp({
                        type: 'delete-supporting-node',
                        nodeId: selectedDto.id,
                      }),
                  });
                }}
              >
                Delete
              </button>
              <button
                type="button"
                style={toolBtn}
                disabled={semanticDisabled || (electricalDraft?.connections.length ?? 0) < 1}
                data-testid="architecture-change-connection-type"
                onClick={() => {
                  if (!electricalDraft?.connections[0]) return;
                  setDraftForm({
                    kind: 'change-connection-type',
                    connectionId: electricalDraft.connections[0].connectionId,
                    connectionType: electricalDraft.connections[0].connectionType,
                  });
                }}
              >
                More…
              </button>
              <button
                type="button"
                style={toolBtn}
                disabled={semanticDisabled || (electricalDraft?.connections.length ?? 0) < 1}
                data-testid="architecture-delete-connection"
                onClick={() => {
                  if (!electricalDraft?.connections[0]) return;
                  setDraftForm({
                    kind: 'delete-connection',
                    connectionId: electricalDraft.connections[0].connectionId,
                  });
                }}
              >
                Delete connection
              </button>
              <button
                type="button"
                style={toolBtn}
                disabled={semanticDisabled || (electricalDraft?.connections.length ?? 0) < 1}
                data-testid="architecture-change-interface-type"
                onClick={() => {
                  if (!electricalDraft?.connections[0]) return;
                  setDraftForm({
                    kind: 'change-interface-type',
                    connectionId: electricalDraft.connections[0].connectionId,
                    interfaceType: electricalDraft.connections[0].interfaceType,
                  });
                }}
              >
                Change interface type
              </button>
              <button
                type="button"
                style={toolBtn}
                disabled={semanticDisabled || (electricalDraft?.connections.length ?? 0) < 1}
                data-testid="architecture-mark-connection-status"
                onClick={() => {
                  if (!electricalDraft?.connections[0]) return;
                  setDraftForm({
                    kind: 'mark-connection-status',
                    connectionId: electricalDraft.connections[0].connectionId,
                    status: electricalDraft.connections[0].status,
                  });
                }}
              >
                Mark connection status
              </button>
            </>
          ) : (
            <span style={{ fontSize: 11, color: t.textMuted, fontWeight: 600 }}>
              Circuit Simulation · provider-backed preview
            </span>
          )}
        </div>
      ) : null}

      {viewId === 'physical' ? (
        <div
          style={{
            padding: '6px 16px',
            borderBottom: `1px solid ${t.border}`,
            background: t.surface2,
            display: 'flex',
            gap: 8,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
          data-testid="architecture-physical-toolbar"
        >
          <span style={{ fontSize: 11, color: t.textMuted, fontWeight: 600 }}>Physical edits</span>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled}
            data-testid="architecture-add-entity"
            onClick={() =>
              setDraftForm({ kind: 'add-entity', name: 'Physical entity', nodeType: 'module' })
            }
          >
            Add entity
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled || !selectedDto}
            data-testid="architecture-delete-entity"
            onClick={() => {
              if (!selectedDto) return;
              setConfirmDialog({
                title: 'Delete entity',
                summary: `Delete entity “${selectedDto.label}”?`,
                confirmLabel: 'Delete',
                destructive: true,
                onConfirm: () =>
                  runPhysicalSemanticOp({ type: 'delete-entity', nodeId: selectedDto.id }),
              });
            }}
          >
            Delete entity
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled}
            data-testid="architecture-add-zone"
            onClick={() => setDraftForm({ kind: 'add-zone', name: 'Zone', zoneKind: 'other' })}
          >
            Add zone
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled || (physicalDraft?.zones.length ?? 0) < 1}
            data-testid="architecture-delete-zone"
            onClick={() => {
              if (!physicalDraft?.zones[0]) return;
              setDraftForm({
                kind: 'delete-zone',
                zoneId: physicalDraft.zones[0].zoneId,
              });
            }}
          >
            Delete zone
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={
              semanticDisabled || !selectedDto || (physicalDraft?.zones.length ?? 0) < 1
            }
            data-testid="architecture-assign-zone"
            onClick={() => {
              if (!selectedDto || !physicalDraft?.zones[0]) return;
              setDraftForm({
                kind: 'assign-zone',
                nodeId: selectedDto.id,
                zoneId: physicalDraft.zones[0].zoneId,
              });
            }}
          >
            Assign selected to zone
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled || !selectedDto || (physicalDraft?.nodes.length ?? 0) < 2}
            data-testid="architecture-add-relationship"
            onClick={() => {
              if (!selectedDto || !physicalDraft) return;
              const toNodeId =
                physicalDraft.nodes.find((n) => n.nodeId !== selectedDto.id)?.nodeId ?? '';
              setDraftForm({
                kind: 'add-relationship',
                fromNodeId: selectedDto.id,
                toNodeId,
                relationshipType: 'adjacent-to',
              });
            }}
          >
            Add relationship
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled || (physicalDraft?.relationships.length ?? 0) < 1}
            data-testid="architecture-change-relationship"
            onClick={() => {
              if (!physicalDraft?.relationships[0]) return;
              setDraftForm({
                kind: 'change-relationship',
                relationshipId: physicalDraft.relationships[0].relationshipId,
                relationshipType: physicalDraft.relationships[0].relationshipType,
              });
            }}
          >
            Change relationship
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled || (physicalDraft?.relationships.length ?? 0) < 1}
            data-testid="architecture-delete-relationship"
            onClick={() => {
              if (!physicalDraft?.relationships[0]) return;
              setDraftForm({
                kind: 'delete-relationship',
                relationshipId: physicalDraft.relationships[0].relationshipId,
              });
            }}
          >
            Delete relationship
          </button>
          <button
            type="button"
            style={toolBtn}
            disabled={semanticDisabled || !selectedDto}
            data-testid="architecture-edit-placement"
            onClick={() => {
              if (!selectedDto || !physicalDraft) return;
              const node = physicalDraft.nodes.find((n) => n.nodeId === selectedDto.id);
              setDraftForm({
                kind: 'edit-placement',
                nodeId: selectedDto.id,
                qualitativePlacement: node?.qualitativePlacement ?? '',
                placementStatus: node?.placementStatus ?? 'provisional',
              });
            }}
          >
            Edit qualitative placement
          </button>
        </div>
      ) : null}

      {draftForm ? (
        <ArchitectureInlineEditor
          form={draftForm}
          setForm={setDraftForm}
          systemDraft={systemDraft}
          electricalDraft={electricalDraft}
          physicalDraft={physicalDraft}
          isDark={isDark}
          disabled={semanticDisabled}
          onSubmit={submitDraftForm}
          onCancel={() => setDraftForm(null)}
        />
      ) : null}

      {confirmDialog ? (
        <ArchitectureConfirmDialog
          dialog={confirmDialog}
          isDark={isDark}
          onDismiss={() => setConfirmDialog(null)}
          onConfirm={() => {
            const action = confirmDialog.onConfirm;
            setConfirmDialog(null);
            action?.();
          }}
        />
      ) : null}

      <div
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: 'minmax(0,1.4fr) minmax(260px,0.8fr)',
          overflow: 'hidden',
        }}
      >
        <div style={{ minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {viewId === 'electrical' && electricalMode === 'simulation' ? (
            <ElectricalSimulationView
              projectId={projectId}
              isDark={isDark}
              currentArtifactVersion={artifact?.artifactVersion}
              onRunSimulation={runCircuitSimulation}
            />
          ) : viewId === 'electrical' && electricalVisualGraph ? (
            <>
              <div style={{ flex: 1, minHeight: 0 }}>
                <ElectricalGraphCanvas
                  nodes={electricalVisualGraph.nodes}
                  edges={electricalVisualGraph.edges}
                  powerRails={electricalVisualGraph.powerRails}
                  isDark={isDark}
                  selectedNodeId={selectedDto?.id ?? null}
                  onSelectNode={(id) => onSelectNode?.(id)}
                  onNodeDragStop={handleLayoutDragStop}
                  onViewportChange={(viewport) => {
                    setLayoutViewport(viewport);
                    if (!artifact) return;
                    saveArchitectureLayout({
                      projectId,
                      artifactType: artifact.artifactType,
                      artifactId: artifact.artifactId,
                      positions: layoutPositions,
                      viewport,
                      activeEntityIds: electricalVisualGraph.nodes.map((n) => n.id),
                    });
                  }}
                />
              </div>
              <ElectricalStatusBar
                isDark={isDark}
                blocking={electricalValidationCounts.blocking}
                warnings={electricalValidationCounts.warnings}
                passed={electricalValidationCounts.passed}
              />
            </>
          ) : (
            <EngineeringGraphCanvas
              nodes={graph.nodes}
              edges={graph.edges}
              isDark={isDark}
              selectedNodeId={selectedDto?.id ?? null}
              onSelectNode={(id) => onSelectNode?.(id)}
              onNodeDragStop={handleLayoutDragStop}
              onViewportChange={(viewport) => {
                setLayoutViewport(viewport);
                if (!artifact) return;
                saveArchitectureLayout({
                  projectId,
                  artifactType: artifact.artifactType,
                  artifactId: artifact.artifactId,
                  positions: layoutPositions,
                  viewport,
                  activeEntityIds: graph.nodes.map((n) => n.id),
                });
              }}
            />
          )}
        </div>
        <aside
          style={{
            borderLeft: `1px solid ${t.border}`,
            overflow: 'auto',
            padding: 16,
            background: t.surface,
          }}
          data-testid="architecture-inspector"
        >
          <ArchitectureInspector
            viewId={viewId}
            artifact={artifact}
            selectedNodeId={selectedDto?.id ?? null}
            draftContent={draftContent}
            isDark={isDark}
            disabled={semanticDisabled}
            onRenameNode={(nodeId, name) =>
              runSystemSemanticOp({ type: 'rename-node', nodeId, name })
            }
            onUpdateFunctionalNode={(nodeId, patch) => {
              if (!isFunctionalDraftContent(draftContent)) return;
              const next = {
                ...draftContent,
                nodes: draftContent.nodes.map((node) =>
                  node.nodeId === nodeId
                    ? {
                        ...node,
                        ...(patch.name != null ? { name: patch.name } : {}),
                        ...(patch.functionalType != null
                          ? { functionalType: patch.functionalType }
                          : {}),
                        ...(patch.responsibilities != null
                          ? {
                              responsibilities: patch.responsibilities as [
                                string,
                                ...string[],
                              ],
                            }
                          : {}),
                      }
                    : node,
                ) as FunctionalArchitectureContent['nodes'],
              };
              void persistDraftContent(recomputeCoverage(next), {
                label: 'edit-node-properties',
              });
            }}
            onEditPlacement={(nodeId, qualitativePlacement, placementStatus) =>
              runPhysicalSemanticOp({
                type: 'edit-placement',
                nodeId,
                qualitativePlacement,
                placementStatus,
              })
            }
            onAssignZone={(nodeId, zoneId) =>
              runPhysicalSemanticOp({ type: 'assign-zone', nodeId, zoneId })
            }
            onChangeConnection={(connectionId, patch) =>
              runElectricalSemanticOp({
                type: 'change-connection',
                connectionId,
                ...patch,
              })
            }
          />
        </aside>
      </div>
    </div>
  );
}


function ArchitectureConfirmDialog({
  dialog,
  isDark,
  onDismiss,
  onConfirm,
}: {
  dialog: ConfirmDialogState;
  isDark: boolean;
  onDismiss: () => void;
  onConfirm: () => void;
}) {
  const t = themeColors(isDark);
  const showConfirm = dialog.destructive !== false && dialog.onConfirm;
  return (
    <div
      data-testid="architecture-confirm-dialog"
      role="dialog"
      aria-modal="true"
      style={{
        padding: '10px 16px',
        borderBottom: `1px solid ${t.border}`,
        background: isDark ? '#2a1f1a' : '#fff8f5',
        display: 'grid',
        gap: 8,
      }}
    >
      <strong style={{ fontSize: 13, color: t.text }}>{dialog.title}</strong>
      {dialog.summary ? (
        <p style={{ margin: 0, fontSize: 12, color: t.textSec, whiteSpace: 'pre-wrap' }}>
          {dialog.summary}
        </p>
      ) : null}
      <div style={{ display: 'flex', gap: 8 }}>
        {showConfirm ? (
          <button
            type="button"
            style={{
              fontSize: 12,
              padding: '4px 10px',
              borderRadius: 6,
              border: `1px solid ${t.border}`,
              background: t.surface,
              color: t.text,
              cursor: 'pointer',
            }}
            onClick={onConfirm}
          >
            {dialog.confirmLabel ?? 'Confirm'}
          </button>
        ) : null}
        <button
          type="button"
          style={{
            fontSize: 12,
            padding: '4px 10px',
            borderRadius: 6,
            border: `1px solid ${t.border}`,
            background: t.surface,
            color: t.text,
            cursor: 'pointer',
          }}
          onClick={onDismiss}
        >
          {showConfirm ? 'Cancel' : 'OK'}
        </button>
      </div>
    </div>
  );
}

function ArchitectureInlineEditor({
  form,
  setForm,
  systemDraft,
  electricalDraft,
  physicalDraft,
  isDark,
  disabled,
  onSubmit,
  onCancel,
}: {
  form: DraftFormState;
  setForm: (next: DraftFormState) => void;
  systemDraft: FunctionalArchitectureContent | null;
  electricalDraft: ElectricalArchitectureContent | null;
  physicalDraft: PhysicalArchitectureContent | null;
  isDark: boolean;
  disabled: boolean;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const t = themeColors(isDark);
  const input = fieldStyle(t);
  const label: CSSProperties = { fontSize: 11, color: t.textMuted, fontWeight: 600 };

  function titleFor(kind: DraftFormState['kind']): string {
    switch (kind) {
      case 'add-node':
        return 'Add node';
      case 'rename-node':
        return 'Rename node';
      case 'add-edge':
        return 'Add edge';
      case 'change-edge-flow':
        return 'Change edge flow';
      case 'delete-edge':
        return 'Delete edge';
      case 'add-supporting-node':
        return 'Add supporting node';
      case 'add-connection':
        return 'Add connection';
      case 'delete-connection':
        return 'Delete connection';
      case 'change-connection-type':
        return 'Change connection type';
      case 'change-interface-type':
        return 'Change interface type';
      case 'mark-connection-status':
        return 'Mark connection status';
      case 'add-entity':
        return 'Add entity';
      case 'add-zone':
        return 'Add zone';
      case 'delete-zone':
        return 'Delete zone';
      case 'assign-zone':
        return 'Assign zone';
      case 'add-relationship':
        return 'Add relationship';
      case 'change-relationship':
        return 'Change relationship';
      case 'delete-relationship':
        return 'Delete relationship';
      case 'edit-placement':
        return 'Edit placement';
      default:
        return 'Edit';
    }
  }

  return (
    <form
      data-testid="architecture-inline-editor"
      onSubmit={(event) => {
        event.preventDefault();
        if (!disabled) onSubmit();
      }}
      style={{
        padding: '10px 16px',
        borderBottom: `1px solid ${t.border}`,
        background: t.surface,
        display: 'grid',
        gap: 8,
        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        alignItems: 'end',
      }}
    >
      <div style={{ gridColumn: '1 / -1', fontSize: 12, fontWeight: 600, color: t.text }}>
        {titleFor(form.kind)}
      </div>

      {form.kind === 'add-node' || form.kind === 'rename-node' || form.kind === 'add-supporting-node' || form.kind === 'add-entity' || form.kind === 'add-zone' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Name</span>
          <input
            style={input}
            value={'name' in form ? form.name : ''}
            disabled={disabled}
            onChange={(e) => {
              if (form.kind === 'add-node') setForm({ ...form, name: e.target.value });
              else if (form.kind === 'rename-node') setForm({ ...form, name: e.target.value });
              else if (form.kind === 'add-supporting-node') setForm({ ...form, name: e.target.value });
              else if (form.kind === 'add-entity') setForm({ ...form, name: e.target.value });
              else if (form.kind === 'add-zone') setForm({ ...form, name: e.target.value });
            }}
          />
        </label>
      ) : null}

      {form.kind === 'add-node' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Functional type</span>
          <select
            style={input}
            value={form.functionalType}
            disabled={disabled}
            onChange={(e) =>
              setForm({
                ...form,
                functionalType: e.target.value as (typeof FUNCTIONAL_TYPES)[number],
              })
            }
          >
            {FUNCTIONAL_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'add-edge' ? (
        <>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={label}>From</span>
            <select
              style={input}
              value={form.fromNodeId}
              disabled={disabled}
              onChange={(e) => setForm({ ...form, fromNodeId: e.target.value })}
            >
              {(systemDraft?.nodes ?? []).map((n) => (
                <option key={n.nodeId} value={n.nodeId}>
                  {n.name}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={label}>To</span>
            <select
              style={input}
              value={form.toNodeId}
              disabled={disabled}
              onChange={(e) => setForm({ ...form, toNodeId: e.target.value })}
            >
              {(systemDraft?.nodes ?? [])
                .filter((n) => n.nodeId !== form.fromNodeId)
                .map((n) => (
                  <option key={n.nodeId} value={n.nodeId}>
                    {n.name}
                  </option>
                ))}
            </select>
          </label>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={label}>Flow type</span>
            <select
              style={input}
              value={form.flowType}
              disabled={disabled}
              onChange={(e) =>
                setForm({ ...form, flowType: e.target.value as (typeof FLOW_TYPES)[number] })
              }
            >
              {FLOW_TYPES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </>
      ) : null}

      {form.kind === 'change-edge-flow' || form.kind === 'delete-edge' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Edge</span>
          <select
            style={input}
            value={form.edgeId}
            disabled={disabled}
            onChange={(e) => setForm({ ...form, edgeId: e.target.value })}
          >
            {(systemDraft?.edges ?? []).map((edge) => (
              <option key={edge.edgeId} value={edge.edgeId}>
                {edge.edgeId} ({edge.flowType})
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'change-edge-flow' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Flow type</span>
          <select
            style={input}
            value={form.flowType}
            disabled={disabled}
            onChange={(e) =>
              setForm({ ...form, flowType: e.target.value as (typeof FLOW_TYPES)[number] })
            }
          >
            {FLOW_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'add-connection' ? (
        <>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={label}>From</span>
            <select
              style={input}
              value={form.fromNodeId}
              disabled={disabled}
              onChange={(e) => setForm({ ...form, fromNodeId: e.target.value })}
            >
              {(electricalDraft?.nodes ?? []).map((n) => (
                <option key={n.nodeId} value={n.nodeId}>
                  {n.name}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={label}>To</span>
            <select
              style={input}
              value={form.toNodeId}
              disabled={disabled}
              onChange={(e) => setForm({ ...form, toNodeId: e.target.value })}
            >
              {(electricalDraft?.nodes ?? [])
                .filter((n) => n.nodeId !== form.fromNodeId)
                .map((n) => (
                  <option key={n.nodeId} value={n.nodeId}>
                    {n.name}
                  </option>
                ))}
            </select>
          </label>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={label}>Connection type</span>
            <select
              style={input}
              value={form.connectionType}
              disabled={disabled}
              onChange={(e) =>
                setForm({
                  ...form,
                  connectionType: e.target.value as (typeof CONNECTION_TYPES)[number],
                })
              }
            >
              {CONNECTION_TYPES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={label}>Interface type</span>
            <select
              style={input}
              value={form.interfaceType}
              disabled={disabled}
              onChange={(e) =>
                setForm({
                  ...form,
                  interfaceType: e.target.value as (typeof INTERFACE_TYPES)[number],
                })
              }
            >
              {INTERFACE_TYPES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </>
      ) : null}

      {form.kind === 'delete-connection' ||
      form.kind === 'change-connection-type' ||
      form.kind === 'change-interface-type' ||
      form.kind === 'mark-connection-status' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Connection</span>
          <select
            style={input}
            value={form.connectionId}
            disabled={disabled}
            onChange={(e) => setForm({ ...form, connectionId: e.target.value })}
          >
            {(electricalDraft?.connections ?? []).map((c) => (
              <option key={c.connectionId} value={c.connectionId}>
                {c.connectionId}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'change-connection-type' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Connection type</span>
          <select
            style={input}
            value={form.connectionType}
            disabled={disabled}
            onChange={(e) =>
              setForm({
                ...form,
                connectionType: e.target.value as (typeof CONNECTION_TYPES)[number],
              })
            }
          >
            {CONNECTION_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'change-interface-type' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Interface type</span>
          <select
            style={input}
            value={form.interfaceType}
            disabled={disabled}
            onChange={(e) =>
              setForm({
                ...form,
                interfaceType: e.target.value as (typeof INTERFACE_TYPES)[number],
              })
            }
          >
            {INTERFACE_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'mark-connection-status' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Status</span>
          <select
            style={input}
            value={form.status}
            disabled={disabled}
            onChange={(e) =>
              setForm({
                ...form,
                status: e.target.value as (typeof CONNECTION_STATUSES)[number],
              })
            }
          >
            {CONNECTION_STATUSES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'add-entity' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Node type</span>
          <select
            style={input}
            value={form.nodeType}
            disabled={disabled}
            onChange={(e) =>
              setForm({
                ...form,
                nodeType: e.target.value as (typeof PHYSICAL_NODE_TYPES)[number],
              })
            }
          >
            {PHYSICAL_NODE_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'add-zone' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Zone kind</span>
          <select
            style={input}
            value={form.zoneKind}
            disabled={disabled}
            onChange={(e) =>
              setForm({ ...form, zoneKind: e.target.value as (typeof ZONE_KINDS)[number] })
            }
          >
            {ZONE_KINDS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'delete-zone' || form.kind === 'assign-zone' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Zone</span>
          <select
            style={input}
            value={form.zoneId}
            disabled={disabled}
            onChange={(e) => setForm({ ...form, zoneId: e.target.value })}
          >
            {(physicalDraft?.zones ?? []).map((z) => (
              <option key={z.zoneId} value={z.zoneId}>
                {z.name} ({z.zoneId})
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'add-relationship' ? (
        <>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={label}>From</span>
            <select
              style={input}
              value={form.fromNodeId}
              disabled={disabled}
              onChange={(e) => setForm({ ...form, fromNodeId: e.target.value })}
            >
              {(physicalDraft?.nodes ?? []).map((n) => (
                <option key={n.nodeId} value={n.nodeId}>
                  {n.name}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={label}>To</span>
            <select
              style={input}
              value={form.toNodeId}
              disabled={disabled}
              onChange={(e) => setForm({ ...form, toNodeId: e.target.value })}
            >
              {(physicalDraft?.nodes ?? [])
                .filter((n) => n.nodeId !== form.fromNodeId)
                .map((n) => (
                  <option key={n.nodeId} value={n.nodeId}>
                    {n.name}
                  </option>
                ))}
            </select>
          </label>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={label}>Relationship type</span>
            <select
              style={input}
              value={form.relationshipType}
              disabled={disabled}
              onChange={(e) =>
                setForm({
                  ...form,
                  relationshipType: e.target.value as (typeof RELATIONSHIP_TYPES)[number],
                })
              }
            >
              {RELATIONSHIP_TYPES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </>
      ) : null}

      {form.kind === 'change-relationship' || form.kind === 'delete-relationship' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Relationship</span>
          <select
            style={input}
            value={form.relationshipId}
            disabled={disabled}
            onChange={(e) => setForm({ ...form, relationshipId: e.target.value })}
          >
            {(physicalDraft?.relationships ?? []).map((r) => (
              <option key={r.relationshipId} value={r.relationshipId}>
                {r.relationshipId} ({r.relationshipType})
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'change-relationship' ? (
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={label}>Relationship type</span>
          <select
            style={input}
            value={form.relationshipType}
            disabled={disabled}
            onChange={(e) =>
              setForm({
                ...form,
                relationshipType: e.target.value as (typeof RELATIONSHIP_TYPES)[number],
              })
            }
          >
            {RELATIONSHIP_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {form.kind === 'edit-placement' ? (
        <>
          <label style={{ display: 'grid', gap: 4, gridColumn: '1 / -1' }}>
            <span style={label}>Qualitative placement</span>
            <textarea
              style={{ ...input, minHeight: 56, resize: 'vertical' }}
              value={form.qualitativePlacement}
              disabled={disabled}
              onChange={(e) => setForm({ ...form, qualitativePlacement: e.target.value })}
            />
          </label>
          <label style={{ display: 'grid', gap: 4 }}>
            <span style={label}>Placement status</span>
            <select
              style={input}
              value={form.placementStatus}
              disabled={disabled}
              onChange={(e) =>
                setForm({
                  ...form,
                  placementStatus: e.target.value as (typeof PLACEMENT_STATUSES)[number],
                })
              }
            >
              {PLACEMENT_STATUSES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </>
      ) : null}

      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button
          type="submit"
          disabled={disabled}
          style={{
            fontSize: 12,
            padding: '4px 10px',
            borderRadius: 6,
            border: `1px solid ${t.border}`,
            background: t.surface,
            color: t.text,
            cursor: disabled ? 'not-allowed' : 'pointer',
            opacity: disabled ? 0.6 : 1,
          }}
        >
          Apply
        </button>
        <button
          type="button"
          style={{
            fontSize: 12,
            padding: '4px 10px',
            borderRadius: 6,
            border: `1px solid ${t.border}`,
            background: t.surface,
            color: t.text,
            cursor: 'pointer',
          }}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function ArchitectureInspector({
  viewId,
  artifact,
  selectedNodeId,
  draftContent,
  isDark,
  disabled = false,
  onRenameNode,
  onUpdateFunctionalNode,
  onEditPlacement,
  onAssignZone,
  onChangeConnection,
}: {
  viewId: ArchitectureViewId;
  artifact: ArchitectureArtifact;
  selectedNodeId: string | null;
  draftContent: ArchitectureDraftContent | null;
  isDark: boolean;
  disabled?: boolean;
  onRenameNode?: (nodeId: string, name: string) => void;
  onUpdateFunctionalNode?: (
    nodeId: string,
    patch: {
      name?: string;
      functionalType?: FunctionalArchitectureContent['nodes'][number]['functionalType'];
      responsibilities?: string[];
    },
  ) => void;
  onEditPlacement?: (
    nodeId: string,
    qualitativePlacement: string,
    placementStatus: PhysicalArchitectureContent['nodes'][number]['placementStatus'],
  ) => void;
  onAssignZone?: (nodeId: string, zoneId: string) => void;
  onChangeConnection?: (
    connectionId: string,
    patch: {
      connectionType?: ElectricalArchitectureContent['connections'][number]['connectionType'];
      interfaceType?: ElectricalArchitectureContent['connections'][number]['interfaceType'];
      status?: ElectricalArchitectureContent['connections'][number]['status'];
    },
  ) => void;
}) {
  const t = themeColors(isDark);
  const input = fieldStyle(t);

  if (artifact.artifactType === 'functional-architecture') {
    const content = isFunctionalDraftContent(draftContent)
      ? draftContent
      : artifact.content;
    const selected = content.nodes.find((n) => n.nodeId === selectedNodeId) ?? content.nodes[0];
    if (!selected) return <p style={{ color: t.textMuted }}>No nodes</p>;
    return (
      <div style={{ display: 'grid', gap: 10 }}>
        <h3 style={{ margin: 0, color: t.text }}>Properties</h3>
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: 11, color: t.textMuted }}>Name</span>
          <input
            style={input}
            defaultValue={selected.name}
            key={`name-${selected.nodeId}-${selected.name}`}
            disabled={disabled}
            onBlur={(e) => {
              const name = e.target.value.trim();
              if (!name || name === selected.name) return;
              onRenameNode?.(selected.nodeId, name);
            }}
          />
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: 11, color: t.textMuted }}>Functional type</span>
          <select
            style={input}
            value={selected.functionalType}
            disabled={disabled}
            onChange={(e) =>
              onUpdateFunctionalNode?.(selected.nodeId, {
                functionalType: e.target
                  .value as FunctionalArchitectureContent['nodes'][number]['functionalType'],
              })
            }
          >
            {FUNCTIONAL_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: 11, color: t.textMuted }}>Responsibilities (one per line)</span>
          <textarea
            style={{ ...input, minHeight: 72, resize: 'vertical' }}
            defaultValue={selected.responsibilities.join('\n')}
            key={`resp-${selected.nodeId}-${selected.responsibilities.join('|')}`}
            disabled={disabled}
            onBlur={(e) => {
              const lines = e.target.value
                .split('\n')
                .map((line) => line.trim())
                .filter(Boolean);
              if (lines.length < 1) return;
              if (lines.join('\n') === selected.responsibilities.join('\n')) return;
              onUpdateFunctionalNode?.(selected.nodeId, { responsibilities: lines });
            }}
          />
        </label>
        <h4 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Requirement coverage</h4>
        <p style={{ margin: 0, fontSize: 12, color: t.text }}>
          {selected.satisfiesRequirementIds.join(', ')}
        </p>
        {content.unresolvedDecisions.length ? (
          <div>
            <h4 style={{ margin: '0 0 6px', fontSize: 12, color: t.textMuted }}>Unresolved decisions</h4>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
              {content.unresolvedDecisions.map((item) => (
                <li key={item.questionId}>{item.displayId ?? item.questionId}</li>
              ))}
            </ul>
          </div>
        ) : null}
        <div>
          <h4 style={{ margin: '0 0 6px', fontSize: 12, color: t.textMuted }}>Flows</h4>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
            {content.edges.map((edge) => {
              const from = content.nodes.find((n) => n.nodeId === edge.fromNodeId)?.name ?? edge.fromNodeId;
              const to = content.nodes.find((n) => n.nodeId === edge.toNodeId)?.name ?? edge.toNodeId;
              return (
                <li key={edge.edgeId}>
                  {from} → {to} ({edge.flowType})
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    );
  }

  if (artifact.artifactType === 'electrical-architecture') {
    const content = isElectricalDraftContent(draftContent)
      ? draftContent
      : artifact.content;
    const selected = content.nodes.find((n) => n.nodeId === selectedNodeId) ?? content.nodes[0];
    if (!selected) return <p style={{ color: t.textMuted }}>No nodes</p>;
    const related = content.connections.filter(
      (c) =>
        !selectedNodeId ||
        c.fromNodeId === selectedNodeId ||
        c.toNodeId === selectedNodeId,
    );
    return (
      <div style={{ display: 'grid', gap: 10 }}>
        <h3 style={{ margin: 0, color: t.text }}>{selected.name}</h3>
        <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>
          {selected.nodeType} · {selected.implementationStatus}
        </p>
        <h4 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Interfaces</h4>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
          {(selected.interfaces ?? []).map((iface) => (
            <li key={iface.interfaceId}>
              {iface.label ?? iface.interfaceId} ({iface.interfaceType}, {iface.direction})
            </li>
          ))}
        </ul>
        <h4 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Linked roles</h4>
        <p style={{ margin: 0, fontSize: 12, color: t.text }}>{selected.componentRoleIds.join(', ') || '—'}</p>
        <h4 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Power domains</h4>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
          {content.powerDomains.map((domain) => (
            <li key={domain.powerDomainId}>
              {domain.name} ({domain.status})
            </li>
          ))}
        </ul>
        <h4 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Connections</h4>
        <div style={{ display: 'grid', gap: 8 }}>
          {related.map((c) => (
            <div
              key={c.connectionId}
              style={{
                border: `1px solid ${t.border}`,
                borderRadius: 6,
                padding: 8,
                display: 'grid',
                gap: 6,
              }}
            >
              <p style={{ margin: 0, fontSize: 11, color: t.textMuted }}>{c.connectionId}</p>
              <p style={{ margin: 0, fontSize: 12, color: t.text }}>
                {c.fromNodeId} → {c.toNodeId}
              </p>
              <label style={{ display: 'grid', gap: 4 }}>
                <span style={{ fontSize: 11, color: t.textMuted }}>Type</span>
                <select
                  style={input}
                  value={c.connectionType}
                  disabled={disabled}
                  onChange={(e) =>
                    onChangeConnection?.(c.connectionId, {
                      connectionType: e.target
                        .value as ElectricalArchitectureContent['connections'][number]['connectionType'],
                    })
                  }
                >
                  {CONNECTION_TYPES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'grid', gap: 4 }}>
                <span style={{ fontSize: 11, color: t.textMuted }}>Interface</span>
                <select
                  style={input}
                  value={c.interfaceType}
                  disabled={disabled}
                  onChange={(e) =>
                    onChangeConnection?.(c.connectionId, {
                      interfaceType: e.target
                        .value as ElectricalArchitectureContent['connections'][number]['interfaceType'],
                    })
                  }
                >
                  {INTERFACE_TYPES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'grid', gap: 4 }}>
                <span style={{ fontSize: 11, color: t.textMuted }}>Status</span>
                <select
                  style={input}
                  value={c.status}
                  disabled={disabled}
                  onChange={(e) =>
                    onChangeConnection?.(c.connectionId, {
                      status: e.target
                        .value as ElectricalArchitectureContent['connections'][number]['status'],
                    })
                  }
                >
                  {CONNECTION_STATUSES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          ))}
        </div>
        {viewId === 'electrical' && content.warnings.length ? (
          <div>
            <h4 style={{ margin: '0 0 6px', fontSize: 12, color: t.textMuted }}>Warnings</h4>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
              {content.warnings.map((w) => (
                <li key={`${w.code}-${w.message}`}>{w.message}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    );
  }

  const content = isPhysicalDraftContent(draftContent) ? draftContent : artifact.content;
  const selected = content.nodes.find((n) => n.nodeId === selectedNodeId) ?? content.nodes[0];
  if (!selected) return <p style={{ color: t.textMuted }}>No nodes</p>;
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <h3 style={{ margin: 0, color: t.text }}>{selected.name}</h3>
      <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>{selected.nodeType}</p>
      <label style={{ display: 'grid', gap: 4 }}>
        <span style={{ fontSize: 11, color: t.textMuted }}>Qualitative placement</span>
        <textarea
          style={{ ...input, minHeight: 56, resize: 'vertical' }}
          defaultValue={selected.qualitativePlacement ?? ''}
          key={`place-${selected.nodeId}-${selected.qualitativePlacement ?? ''}`}
          disabled={disabled}
          onBlur={(e) => {
            const value = e.target.value;
            if (value === (selected.qualitativePlacement ?? '')) return;
            onEditPlacement?.(selected.nodeId, value, selected.placementStatus);
          }}
        />
      </label>
      <label style={{ display: 'grid', gap: 4 }}>
        <span style={{ fontSize: 11, color: t.textMuted }}>Placement status</span>
        <select
          style={input}
          value={selected.placementStatus}
          disabled={disabled}
          onChange={(e) =>
            onEditPlacement?.(
              selected.nodeId,
              selected.qualitativePlacement ?? '',
              e.target.value as PhysicalArchitectureContent['nodes'][number]['placementStatus'],
            )
          }
        >
          {PLACEMENT_STATUSES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </label>
      <label style={{ display: 'grid', gap: 4 }}>
        <span style={{ fontSize: 11, color: t.textMuted }}>Zone</span>
        <select
          style={input}
          value={selected.zoneId ?? ''}
          disabled={disabled || content.zones.length < 1}
          onChange={(e) => {
            if (!e.target.value) return;
            onAssignZone?.(selected.nodeId, e.target.value);
          }}
        >
          <option value="">Unassigned</option>
          {content.zones.map((zone) => (
            <option key={zone.zoneId} value={zone.zoneId}>
              {zone.name} ({zone.zoneKind})
            </option>
          ))}
        </select>
      </label>
      <h4 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Zones</h4>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
        {content.zones.map((zone) => (
          <li key={zone.zoneId}>
            {zone.name} ({zone.zoneKind})
          </li>
        ))}
      </ul>
      <h4 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Relationships</h4>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
        {content.relationships
          .filter(
            (r) =>
              !selectedNodeId ||
              r.fromNodeId === selectedNodeId ||
              r.toNodeId === selectedNodeId,
          )
          .map((r) => (
            <li key={r.relationshipId}>
              {r.fromNodeId} → {r.toNodeId} ({r.relationshipType})
            </li>
          ))}
      </ul>
    </div>
  );
}
