import type { GraphLayoutState, GraphLayoutPositions, GraphLayoutViewport } from './types';

/**
 * Phase 13A layout persistence.
 *
 * Layout is NOT an artifact revision and is NOT keyed by artifact revision / version.
 * Storage identity: project + artifactType + artifactId (stable artifact identity).
 * Positions inside the layout are keyed by stable architecture entity IDs
 * (nodeId / enode / pnode). Surviving entity IDs retain positions across accepted
 * semantic revisions without copy-forward logic tied to revision numbers.
 *
 * Prefer a future backend:
 *   GET/PUT /v1/projects/:id/architecture-layouts/:artifactType/:artifactId
 * Until then, localStorage is acceptable for Phase 13A.
 */
export function layoutStorageKey(
  projectId: string,
  artifactType: string,
  artifactId: string,
): string {
  return `nexus:arch-layout:${projectId}:${artifactType}:${artifactId}`;
}

/** Previous Phase 13A key without artifactId — migrate forward to avoid type collisions. */
export function typeOnlyLayoutStorageKey(projectId: string, artifactType: string): string {
  return `nexus:arch-layout:${projectId}:${artifactType}`;
}

export function loadLayoutFromLocalStorage(key: string): GraphLayoutState | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as GraphLayoutState;
    if (!parsed || typeof parsed !== 'object' || typeof parsed.positions !== 'object') {
      return null;
    }
    return {
      positions: parsed.positions ?? {},
      viewport: parsed.viewport,
      updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

export function saveLayoutToLocalStorage(key: string, state: GraphLayoutState): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(key, JSON.stringify(state));
}

export type LayoutSaveInput = {
  projectId: string;
  artifactType: string;
  artifactId: string;
  positions: GraphLayoutPositions;
  viewport?: GraphLayoutViewport;
  /** When provided, prune positions for deleted entities and keep survivors. */
  activeEntityIds?: readonly string[];
};

/**
 * Reconcile layout positions with the current semantic entity set.
 * - surviving IDs keep positions
 * - deleted IDs are removed
 * - new IDs are omitted (caller assigns defaults via adapters)
 */
export function reconcileLayoutPositions(
  positions: GraphLayoutPositions,
  activeEntityIds: readonly string[],
): GraphLayoutPositions {
  const active = new Set(activeEntityIds);
  const next: GraphLayoutPositions = {};
  for (const [id, pos] of Object.entries(positions)) {
    if (active.has(id)) next[id] = pos;
  }
  return next;
}

/**
 * Persist layout only. Must never call artifact propose/accept or submitArtifactCommand.
 * Must never emit Project Ledger engineering events.
 */
export function saveArchitectureLayout(input: LayoutSaveInput): GraphLayoutState {
  const positions =
    input.activeEntityIds != null
      ? reconcileLayoutPositions(input.positions, input.activeEntityIds)
      : input.positions;
  const state: GraphLayoutState = {
    positions,
    viewport: input.viewport,
    updatedAt: new Date().toISOString(),
  };
  const key = layoutStorageKey(input.projectId, input.artifactType, input.artifactId);
  saveLayoutToLocalStorage(key, state);
  return state;
}

function findSiblingLayout(
  projectId: string,
  artifactType: string,
  excludeArtifactId: string,
): GraphLayoutState | null {
  if (typeof localStorage === 'undefined') return null;
  const prefix = `nexus:arch-layout:${projectId}:${artifactType}:`;
  let best: GraphLayoutState | null = null;
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (!key || !key.startsWith(prefix)) continue;
    const siblingId = key.slice(prefix.length);
    if (!siblingId || siblingId === excludeArtifactId || siblingId.includes(':')) continue;
    const loaded = loadLayoutFromLocalStorage(key);
    if (!loaded) continue;
    if (!best || loaded.updatedAt > best.updatedAt) best = loaded;
  }
  return best;
}

/**
 * Load layout for a stable artifact identity.
 * Entity positions survive across accepted revisions when entity IDs survive:
 * if the current artifactId has no layout yet, migrate from type-only legacy
 * storage or from a sibling artifactId layout (prior accepted head).
 */
export function loadArchitectureLayout(
  projectId: string,
  artifactType: string,
  artifactId: string,
): GraphLayoutState | null {
  const primaryKey = layoutStorageKey(projectId, artifactType, artifactId);
  const primary = loadLayoutFromLocalStorage(primaryKey);
  if (primary) return primary;

  const typeOnly = loadLayoutFromLocalStorage(typeOnlyLayoutStorageKey(projectId, artifactType));
  if (typeOnly) {
    saveLayoutToLocalStorage(primaryKey, typeOnly);
    localStorage.removeItem(typeOnlyLayoutStorageKey(projectId, artifactType));
    return typeOnly;
  }

  const sibling = findSiblingLayout(projectId, artifactType, artifactId);
  if (sibling) {
    // Carry entity-keyed positions forward to the new accepted artifact identity.
    saveLayoutToLocalStorage(primaryKey, sibling);
    return sibling;
  }

  return null;
}

export function resetArchitectureLayout(
  projectId: string,
  artifactType: string,
  artifactId: string,
): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(layoutStorageKey(projectId, artifactType, artifactId));
}

/** Merge saved positions onto DTO nodes (dto positions are defaults for new IDs). */
export function applyLayoutPositions<T extends { id: string; position?: { x: number; y: number } }>(
  nodes: T[],
  positions: GraphLayoutPositions | undefined,
): T[] {
  if (!positions) return nodes;
  return nodes.map((node) => {
    const saved = positions[node.id];
    if (!saved) return node;
    return { ...node, position: { x: saved.x, y: saved.y } };
  });
}
