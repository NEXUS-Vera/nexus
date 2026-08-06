import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { ArtifactRouteKey, GlobalView } from '../artifacts/types';
import { ARTIFACT_REGISTRY, isArtifactRouteKey } from '../artifacts/registry';
import type { InspectorSelection } from '../lib/inspector-selection';

const DEFAULT_ARTIFACT: ArtifactRouteKey = 'project-brief';

function parseGlobalView(value: string | null): GlobalView {
  if (value === 'overview' || value === 'mind-graph' || value === 'workspace') return value;
  return 'workspace';
}

function parseSelection(params: URLSearchParams): InspectorSelection {
  const kind = params.get('sel');
  const id = params.get('selId');
  if (!kind || kind === 'none') return { kind: 'none' };
  if (kind === 'next-action') return { kind: 'next-action' };
  if (kind === 'artifact-revision') {
    const artifactType = params.get('revType');
    const version = Number(params.get('revVersion'));
    if (artifactType && Number.isFinite(version) && version >= 1) {
      return { kind: 'artifact-revision', artifactType, version };
    }
    return { kind: 'none' };
  }
  if (
    id &&
    (kind === 'requirement' ||
      kind === 'architecture-node' ||
      kind === 'component-role' ||
      kind === 'open-question' ||
      kind === 'validation-issue' ||
      kind === 'project-brief-item')
  ) {
    return { kind, id };
  }
  return { kind: 'none' };
}

export function useWorkspaceUrl() {
  const [searchParams, setSearchParams] = useSearchParams();

  const globalView = parseGlobalView(searchParams.get('view'));
  const artifactParam = searchParams.get('artifact');
  const selectedArtifact: ArtifactRouteKey = isArtifactRouteKey(artifactParam)
    ? artifactParam
    : DEFAULT_ARTIFACT;
  const selectedRequirement = searchParams.get('req');
  const selectedArchNode = searchParams.get('node');
  const selectedComponentRole = searchParams.get('role');
  const selectedTest = searchParams.get('test');
  const selectedRisk = searchParams.get('risk');
  const historyOpen = searchParams.get('history') === '1';
  const selection = useMemo(() => parseSelection(searchParams), [searchParams]);

  const patchParams = useCallback(
    (updates: Record<string, string | null | undefined>, replace = false) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(updates)) {
            if (value == null || value === '') next.delete(key);
            else next.set(key, value);
          }
          return next;
        },
        { replace },
      );
    },
    [setSearchParams],
  );

  const setGlobalView = useCallback(
    (view: GlobalView) => {
      patchParams({ view: view === 'workspace' ? null : view });
    },
    [patchParams],
  );

  const setSelectedArtifact = useCallback(
    (artifact: ArtifactRouteKey) => {
      const entry = ARTIFACT_REGISTRY[artifact];
      patchParams({
        view: null,
        artifact: entry.routeKey,
        req: null,
        node: null,
        role: null,
        test: null,
        risk: null,
        sel: null,
        selId: null,
      });
    },
    [patchParams],
  );

  const setSelectedRequirement = useCallback(
    (id: string | null) => {
      patchParams({
        view: null,
        artifact: 'requirement-set',
        req: id,
        sel: id ? 'requirement' : null,
        selId: id,
      });
    },
    [patchParams],
  );

  const setSelectedArchNode = useCallback(
    (id: string | null) => {
      patchParams({
        view: null,
        artifact: 'functional-architecture',
        node: id,
        sel: id ? 'architecture-node' : null,
        selId: id,
      });
    },
    [patchParams],
  );

  const setSelectedComponentRole = useCallback(
    (id: string | null) => {
      patchParams({
        view: null,
        artifact: 'component-plan',
        role: id,
        sel: id ? 'component-role' : null,
        selId: id,
      });
    },
    [patchParams],
  );

  const setInspectorSelection = useCallback(
    (next: InspectorSelection) => {
      if (next.kind === 'none') {
        patchParams({ sel: null, selId: null, revType: null, revVersion: null });
        return;
      }
      if (next.kind === 'next-action') {
        patchParams({ sel: 'next-action', selId: null, revType: null, revVersion: null });
        return;
      }
      if (next.kind === 'artifact-revision') {
        patchParams({
          sel: 'artifact-revision',
          selId: null,
          revType: next.artifactType,
          revVersion: String(next.version),
          history: '1',
        });
        return;
      }
      patchParams({
        sel: next.kind,
        selId: next.id,
        revType: null,
        revVersion: null,
      });
    },
    [patchParams],
  );

  const setHistoryOpen = useCallback(
    (open: boolean) => {
      patchParams({ history: open ? '1' : null });
    },
    [patchParams],
  );

  const focusVera = useCallback(() => {
    patchParams({ view: null });
    requestAnimationFrame(() => {
      document.getElementById('vera-turn')?.focus();
    });
  }, [patchParams]);

  return {
    globalView,
    selectedArtifact,
    selectedRequirement,
    selectedArchNode,
    selectedComponentRole,
    selectedTest,
    selectedRisk,
    historyOpen,
    selection,
    setGlobalView,
    setSelectedArtifact,
    setSelectedRequirement,
    setSelectedArchNode,
    setSelectedComponentRole,
    setInspectorSelection,
    setHistoryOpen,
    focusVera,
    patchParams,
  };
}
