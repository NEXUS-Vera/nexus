import { describe, expect, it } from 'vitest';
import type {
  ElectricalArchitectureContent,
  FunctionalArchitectureContent,
  PhysicalArchitectureContent,
} from '@nexus/contracts';
import {
  applyElectricalSemanticOp,
  applyPhysicalSemanticOp,
  applySemanticOp,
  recomputeCoverage,
} from './workspace';

function minimalFunctional(): FunctionalArchitectureContent {
  return {
    architectureId: 'farch_test',
    architectureMaturity: 'provisional',
    systemBoundary: 'Test system',
    nodes: [
      {
        nodeId: 'node_a',
        name: 'A',
        functionalType: 'processing',
        responsibilities: ['r1'],
        satisfiesRequirementIds: ['req_1'],
      },
      {
        nodeId: 'node_b',
        name: 'B',
        functionalType: 'sensing',
        responsibilities: ['r2'],
        satisfiesRequirementIds: ['req_1'],
      },
    ],
    edges: [
      {
        edgeId: 'edge_1',
        fromNodeId: 'node_a',
        toNodeId: 'node_b',
        flowType: 'data',
        description: 'flow',
      },
    ],
    requirementCoverage: { coveredRequirementIds: ['req_1'] },
    unresolvedDecisions: [],
    assumptions: [],
    openTradeoffs: [],
  } as unknown as FunctionalArchitectureContent;
}

function minimalElectrical(): ElectricalArchitectureContent {
  return {
    architectureId: 'earch_test',
    maturity: 'provisional',
    summary: 'test',
    selectionBasisSummary: 'test',
    evidenceStatus: 'unverified',
    nodes: [
      {
        nodeId: 'enode_a',
        name: 'MCU',
        nodeType: 'component',
        functionalArchitectureNodeIds: [],
        componentRoleIds: ['role_1'],
        implementationStatus: 'preferred',
        evidenceStatus: 'unverified',
      },
      {
        nodeId: 'enode_b',
        name: 'Support',
        nodeType: 'supporting-electronics',
        functionalArchitectureNodeIds: [],
        componentRoleIds: [],
        implementationStatus: 'unresolved',
        evidenceStatus: 'unverified',
      },
    ],
    connections: [],
    powerDomains: [],
    coverageSummary: {
      totalFunctionalNodes: 0,
      coveredFunctionalNodes: 0,
      uncoveredFunctionalNodeIds: [],
      unresolvedConnectionCount: 0,
      unresolvedImplementationCount: 0,
      preferredImplementationCount: 0,
      approvedImplementationCount: 0,
    },
    unresolvedDecisions: [],
    warnings: [],
    assumptions: [],
  };
}

function minimalPhysical(): PhysicalArchitectureContent {
  return {
    architectureId: 'parch_test',
    maturity: 'provisional',
    summary: 'test',
    evidenceStatus: 'unverified',
    nodes: [
      {
        nodeId: 'pnode_a',
        name: 'Board',
        nodeType: 'board',
        electricalNodeIds: [],
        placementStatus: 'unresolved',
      },
    ],
    zones: [],
    relationships: [],
    coverageSummary: {
      totalElectricalNodes: 0,
      coveredElectricalNodes: 0,
      uncoveredElectricalNodeIds: [],
      unresolvedPlacementCount: 1,
      provisionalRelationshipCount: 0,
    },
    unresolvedDecisions: [],
    warnings: [],
    assumptions: [],
  };
}

describe('architecture workspace semantic ops', () => {
  it('renames functional nodes and recomputes coverage', () => {
    const next = recomputeCoverage(
      applySemanticOp(minimalFunctional(), {
        type: 'rename-node',
        nodeId: 'node_a',
        name: 'Renamed',
      }),
    );
    expect(next.nodes.find((n) => n.nodeId === 'node_a')?.name).toBe('Renamed');
    expect(next.requirementCoverage.coveredRequirementIds).toContain('req_1');
  });

  it('adds supporting electrical nodes and blocks role-bound deletes', () => {
    const withSupport = applyElectricalSemanticOp(minimalElectrical(), {
      type: 'add-supporting-node',
      name: 'Filter',
    });
    expect(withSupport.nodes.some((n) => n.name === 'Filter')).toBe(true);

    expect(() =>
      applyElectricalSemanticOp(minimalElectrical(), {
        type: 'delete-supporting-node',
        nodeId: 'enode_a',
      }),
    ).toThrow(/Component Role/);

    const deleted = applyElectricalSemanticOp(minimalElectrical(), {
      type: 'delete-supporting-node',
      nodeId: 'enode_b',
    });
    expect(deleted.nodes.find((n) => n.nodeId === 'enode_b')).toBeUndefined();
  });

    it('adds physical zones and assigns entities', () => {
    const withZone = applyPhysicalSemanticOp(minimalPhysical(), {
      type: 'add-zone',
      name: 'Enclosure',
    });
    const zoneId = withZone.zones[0]?.zoneId;
    expect(zoneId).toBeTruthy();
    const assigned = applyPhysicalSemanticOp(withZone, {
      type: 'assign-zone',
      nodeId: 'pnode_a',
      zoneId: zoneId!,
    });
    expect(assigned.nodes[0]?.zoneId).toBe(zoneId);
    expect(assigned.zones[0]?.memberNodeIds).toContain('pnode_a');
  });

  it('deletes zones and changes relationships', () => {
    let content = applyPhysicalSemanticOp(minimalPhysical(), {
      type: 'add-zone',
      name: 'Bay',
    });
    const zoneId = content.zones[0]!.zoneId;
    content = applyPhysicalSemanticOp(content, {
      type: 'assign-zone',
      nodeId: 'pnode_a',
      zoneId,
    });
    content = applyPhysicalSemanticOp(content, {
      type: 'add-entity',
      name: 'Other',
    });
    const otherId = content.nodes.find((n) => n.nodeId !== 'pnode_a')!.nodeId;
    content = applyPhysicalSemanticOp(content, {
      type: 'add-relationship',
      fromNodeId: 'pnode_a',
      toNodeId: otherId,
      relationshipType: 'adjacent-to',
    });
    const relId = content.relationships[0]!.relationshipId;
    content = applyPhysicalSemanticOp(content, {
      type: 'change-relationship',
      relationshipId: relId,
      relationshipType: 'mounted-on',
    });
    expect(content.relationships[0]?.relationshipType).toBe('mounted-on');
    content = applyPhysicalSemanticOp(content, { type: 'delete-zone', zoneId });
    expect(content.zones.find((z) => z.zoneId === zoneId)).toBeUndefined();
    expect(content.nodes.find((n) => n.nodeId === 'pnode_a')?.zoneId).toBeUndefined();
  });

  it('supports remove-and-reconcile for functional nodes', () => {
    const next = applySemanticOp(minimalFunctional(), {
      type: 'remove-and-reconcile',
      nodeId: 'node_a',
    });
    expect(next.nodes.find((n) => n.nodeId === 'node_a')).toBeUndefined();
    expect(next.nodes.find((n) => n.nodeId === 'node_b')).toBeTruthy();
  });
});
