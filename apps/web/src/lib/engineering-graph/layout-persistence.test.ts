import { beforeEach, describe, expect, it, vi } from 'vitest';
import { layoutPositionsAfterDrag } from './EngineeringGraphCanvas';
import {
  applyLayoutPositions,
  layoutStorageKey,
  loadArchitectureLayout,
  reconcileLayoutPositions,
  resetArchitectureLayout,
  saveArchitectureLayout,
  typeOnlyLayoutStorageKey,
} from './layout-persistence';

describe('architecture layout persistence', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('keys layout by project + artifactType + artifactId, not revision version', () => {
    const submitArtifactCommand = vi.fn();

    saveArchitectureLayout({
      projectId: 'proj_1',
      artifactType: 'functional-architecture',
      artifactId: 'art_stable_identity',
      positions: { node_stable: { x: 12, y: 34 } },
      viewport: { x: 0, y: 0, zoom: 1 },
    });

    expect(layoutStorageKey('proj_1', 'functional-architecture', 'art_stable_identity')).toBe(
      'nexus:arch-layout:proj_1:functional-architecture:art_stable_identity',
    );

    // Same artifact identity still loads positions (no revision id in key).
    const loaded = loadArchitectureLayout(
      'proj_1',
      'functional-architecture',
      'art_stable_identity',
    );
    expect(loaded?.positions.node_stable).toEqual({ x: 12, y: 34 });
    expect(submitArtifactCommand).not.toHaveBeenCalled();
  });

  it('isolates layouts for different artifactIds of the same type', () => {
    saveArchitectureLayout({
      projectId: 'proj_m',
      artifactType: 'functional-architecture',
      artifactId: 'art_a',
      positions: { node_x: { x: 1, y: 1 } },
    });
    saveArchitectureLayout({
      projectId: 'proj_m',
      artifactType: 'functional-architecture',
      artifactId: 'art_b',
      positions: { node_x: { x: 9, y: 9 } },
    });
    expect(
      loadArchitectureLayout('proj_m', 'functional-architecture', 'art_a')?.positions.node_x,
    ).toEqual({ x: 1, y: 1 });
    expect(
      loadArchitectureLayout('proj_m', 'functional-architecture', 'art_b')?.positions.node_x,
    ).toEqual({ x: 9, y: 9 });
  });

  it('preserves entity positions across accepted artifact identity change', () => {
    saveArchitectureLayout({
      projectId: 'proj_rev',
      artifactType: 'electrical-architecture',
      artifactId: 'art_v1',
      positions: { enode_keep: { x: 40, y: 50 }, enode_gone: { x: 1, y: 2 } },
    });
    // New accepted revision gets a new artifactId; entity-keyed positions carry forward.
    const loaded = loadArchitectureLayout('proj_rev', 'electrical-architecture', 'art_v2');
    expect(loaded?.positions.enode_keep).toEqual({ x: 40, y: 50 });
    expect(
      localStorage.getItem(
        layoutStorageKey('proj_rev', 'electrical-architecture', 'art_v2'),
      ),
    ).toBeTruthy();
  });

  it('migrates type-only legacy keys into artifactId keys', () => {
    localStorage.setItem(
      typeOnlyLayoutStorageKey('proj_legacy', 'physical-architecture'),
      JSON.stringify({
        positions: { pnode_1: { x: 7, y: 8 } },
        updatedAt: '2026-01-01T00:00:00.000Z',
      }),
    );
    const loaded = loadArchitectureLayout(
      'proj_legacy',
      'physical-architecture',
      'art_new',
    );
    expect(loaded?.positions.pnode_1).toEqual({ x: 7, y: 8 });
    expect(
      localStorage.getItem(typeOnlyLayoutStorageKey('proj_legacy', 'physical-architecture')),
    ).toBeNull();
    expect(
      localStorage.getItem(
        layoutStorageKey('proj_legacy', 'physical-architecture', 'art_new'),
      ),
    ).toBeTruthy();
  });

  it('preserves surviving IDs and prunes deleted IDs on reconcile', () => {
    const positions = {
      node_keep: { x: 1, y: 2 },
      node_gone: { x: 3, y: 4 },
      node_also: { x: 5, y: 6 },
    };
    const next = reconcileLayoutPositions(positions, ['node_keep', 'node_new']);
    expect(next).toEqual({ node_keep: { x: 1, y: 2 } });
    expect(next.node_gone).toBeUndefined();
    expect(next.node_new).toBeUndefined();
  });

  it('save with activeEntityIds prunes stale layout entries', () => {
    saveArchitectureLayout({
      projectId: 'proj_p',
      artifactType: 'electrical-architecture',
      artifactId: 'art_e',
      positions: {
        enode_a: { x: 10, y: 10 },
        enode_deleted: { x: 20, y: 20 },
      },
      activeEntityIds: ['enode_a', 'enode_new'],
    });
    const loaded = loadArchitectureLayout('proj_p', 'electrical-architecture', 'art_e');
    expect(loaded?.positions).toEqual({ enode_a: { x: 10, y: 10 } });
  });

  it('reset clears layout without touching semantic content helpers', () => {
    saveArchitectureLayout({
      projectId: 'proj_r',
      artifactType: 'physical-architecture',
      artifactId: 'art_p',
      positions: { pnode_1: { x: 1, y: 1 } },
    });
    resetArchitectureLayout('proj_r', 'physical-architecture', 'art_p');
    expect(loadArchitectureLayout('proj_r', 'physical-architecture', 'art_p')).toBeNull();
  });

  it('proves onNodeDragStop-style handlers only call layout save', () => {
    const submitArtifactCommand = vi.fn();
    const saveLayout = vi.fn((positions: Record<string, { x: number; y: number }>) => {
      return saveArchitectureLayout({
        projectId: 'proj_drag',
        artifactType: 'electrical-architecture',
        artifactId: 'art_drag',
        positions,
      });
    });

    const afterDrag = layoutPositionsAfterDrag([
      { id: 'n1', position: { x: 40, y: 50 } },
      { id: 'n2', position: { x: 80, y: 90 } },
    ]);
    saveLayout(afterDrag);

    expect(saveLayout).toHaveBeenCalledTimes(1);
    expect(submitArtifactCommand).not.toHaveBeenCalled();
    expect(
      loadArchitectureLayout('proj_drag', 'electrical-architecture', 'art_drag')?.positions.n1,
    ).toEqual({ x: 40, y: 50 });
  });

  it('applies saved positions onto dto nodes; new ids keep defaults', () => {
    const nodes = [
      { id: 'a', label: 'A', position: { x: 0, y: 0 } },
      { id: 'b', label: 'B', position: { x: 10, y: 10 } },
    ];
    const next = applyLayoutPositions(nodes, { a: { x: 99, y: 88 } });
    expect(next[0].position).toEqual({ x: 99, y: 88 });
    expect(next[1].position).toEqual({ x: 10, y: 10 });
  });
});
