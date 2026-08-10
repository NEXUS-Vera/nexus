import { describe, expect, it } from 'vitest';
import type {
  ElectricalArchitectureContent,
  FunctionalArchitectureContent,
  PhysicalArchitectureContent,
} from '@nexus/contracts';
import functionalFixture from '../../../../../packages/contracts/examples/valid/greenhouse-sensing-node/functional-architecture-artifact.json';
import electricalFixture from '../../../../../packages/contracts/examples/valid/phase-13-electrical-architecture/electrical-architecture-artifact.json';
import physicalFixture from '../../../../../packages/contracts/examples/valid/phase-13-physical-architecture/physical-architecture-artifact.json';
import {
  adaptElectricalArchitecture,
  adaptFunctionalArchitecture,
  adaptPhysicalArchitecture,
} from './adapters';

describe('engineering-graph adapters', () => {
  it('adapts functional architecture without react-flow types', () => {
    const content = functionalFixture.content as unknown as FunctionalArchitectureContent;
    const graph = adaptFunctionalArchitecture(content);
    expect(graph.nodes.length).toBe(content.nodes.length);
    expect(graph.edges.length).toBe(content.edges.length);
    expect(graph.nodes[0]).toMatchObject({
      id: content.nodes[0].nodeId,
      label: content.nodes[0].name,
      kind: 'functional-node',
      semanticType: content.nodes[0].functionalType,
    });
    expect(graph.edges[0]).toMatchObject({
      id: content.edges[0].edgeId,
      source: content.edges[0].fromNodeId,
      target: content.edges[0].toNodeId,
    });
    // Canonical DTOs must not leak React Flow fields.
    expect(graph.nodes[0]).not.toHaveProperty('measured');
    expect(graph.nodes[0]).not.toHaveProperty('selected');
    expect(JSON.stringify(graph)).not.toMatch(/react-flow|xyflow/i);
  });

  it('adapts electrical architecture connections', () => {
    const content = electricalFixture.content as unknown as ElectricalArchitectureContent;
    const graph = adaptElectricalArchitecture(content);
    expect(graph.nodes.length).toBe(content.nodes.length);
    expect(graph.edges.length).toBe(content.connections.length);
    expect(graph.nodes.every((n) => n.kind === 'electrical-node')).toBe(true);
    expect(graph.edges[0]?.edgeType).toBe(content.connections[0]?.connectionType);
  });

  it('does not crash on absent or partial electrical/physical content', () => {
    expect(adaptElectricalArchitecture(undefined).nodes).toEqual([]);
    expect(adaptElectricalArchitecture(null).edges).toEqual([]);
    expect(adaptElectricalArchitecture({} as ElectricalArchitectureContent).nodes).toEqual([]);
    expect(
      adaptElectricalArchitecture({ nodes: undefined, connections: undefined } as never).edges,
    ).toEqual([]);
    expect(adaptPhysicalArchitecture(undefined).nodes).toEqual([]);
    expect(adaptPhysicalArchitecture({ nodes: [], relationships: undefined } as never).edges).toEqual(
      [],
    );
    expect(adaptFunctionalArchitecture(undefined).nodes).toEqual([]);
  });

  it('adapts physical architecture relationships', () => {
    const content = physicalFixture.content as unknown as PhysicalArchitectureContent;
    const graph = adaptPhysicalArchitecture(content);
    expect(graph.nodes.length).toBe(content.nodes.length);
    expect(graph.edges.length).toBe(content.relationships.length);
    expect(graph.nodes.every((n) => n.kind === 'physical-node')).toBe(true);
    expect(graph.edges[0]?.label).toBe(content.relationships[0]?.relationshipType);
  });
});
