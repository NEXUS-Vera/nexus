import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { ArtifactRouteKey, GlobalView } from '../artifacts/types';
import { ARTIFACT_REGISTRY, isArtifactRouteKey } from '../artifacts/registry';
import {
  artifactTypeFromView,
  isArchitectureViewId,
  viewFromArtifactType,
  type ArchitectureViewId,
} from '../artifacts/architecture/views';
import type { InspectorSelection } from '../lib/inspector-selection';

const DEFAULT_ARTIFACT: ArtifactRouteKey = 'project-brief';

export type InspectorPanelMode = 'context' | 'vera';

const ARCHITECTURE_SELECTION_KINDS = new Set([
  'architecture-node',
  'functional-edge',
  'electrical-node',
  'electrical-connection',
  'power-domain',
  'physical-node',
  'physical-relationship',
  'architecture-view',
  'component-role',
  'open-question',
  'validation-issue',
  'project-brief-item',
  'requirement',
]);

function parseArchitectureView(value: string | null): ArchitectureViewId | null {
  if (isArchitectureViewId(value)) return value;
  return null;
}

/**
 * Global chrome views: overview | mind-graph | workspace.
 * Architecture System/Electrical/Physical reuse the `view` param and map to workspace mode.
 */
function parseGlobalView(value: string | null): GlobalView {
  if (value === 'overview' || value === 'mind-graph') return value;
  if (isArchitectureViewId(value) || value === 'workspace' || value == null || value === '') {
    return 'workspace';
  }
  return 'workspace';
}

function parseInspectorPanel(value: string | null): InspectorPanelMode {
  if (value === 'vera') return 'vera';
  return 'context';
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
  if (id && ARCHITECTURE_SELECTION_KINDS.has(kind)) {
    return { kind: kind as Exclude<InspectorSelection, { kind: 'none' | 'next-action' | 'artifact-revision' }>['kind'], id };
  }
  return { kind: 'none' };
}

function selectionKindForArchitectureView(view: ArchitectureViewId): InspectorSelection['kind'] {
  if (view === 'electrical') return 'electrical-node';
  if (view === 'physical') return 'physical-node';
  return 'architecture-node';
}

export function useWorkspaceUrl() {
  const [searchParams, setSearchParams] = useSearchParams();

  const viewParam = searchParams.get('view');
  const globalView = parseGlobalView(viewParam);
  const architectureViewFromParam = parseArchitectureView(viewParam);
  const artifactParamRaw = searchParams.get('artifact');
  // Legacy Phase 14/16 placeholder routes → live workspaces.
  const artifactParam =
    artifactParamRaw === 'firmware-scaffold'
      ? 'firmware'
      : artifactParamRaw === 'analysis-notebook'
        ? 'analysis'
        : artifactParamRaw;
  const selectedArtifact: ArtifactRouteKey = isArtifactRouteKey(artifactParam)
    ? artifactParam
    : DEFAULT_ARTIFACT;

  const selectedArchitectureView: ArchitectureViewId | null = useMemo(() => {
    if (architectureViewFromParam) return architectureViewFromParam;
    return viewFromArtifactType(selectedArtifact);
  }, [architectureViewFromParam, selectedArtifact]);

  const selectedRequirement = searchParams.get('req');
  const selectedArchNode = searchParams.get('node');
  const selectedComponentRole = searchParams.get('role');
  const selectedTest = searchParams.get('test');
  const selectedRisk = searchParams.get('risk');
  const historyOpen = searchParams.get('history') === '1';
  const inspectorPanel = parseInspectorPanel(searchParams.get('panel'));
  const electricalMode =
    selectedArchitectureView === 'electrical' && searchParams.get('mode') === 'simulation'
      ? ('simulation' as const)
      : ('design' as const);
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

  const setArchitectureView = useCallback(
    (view: ArchitectureViewId) => {
      patchParams({
        view,
        artifact: artifactTypeFromView(view),
        req: null,
        role: null,
        test: null,
        risk: null,
        sel: null,
        selId: null,
        mode: null,
      });
    },
    [patchParams],
  );

  const setElectricalMode = useCallback(
    (mode: 'design' | 'simulation') => {
      patchParams({
        view: 'electrical',
        artifact: 'electrical-architecture',
        mode: mode === 'design' ? null : 'simulation',
      });
    },
    [patchParams],
  );

  const setSelectedArtifact = useCallback(
    (artifact: ArtifactRouteKey) => {
      const entry = ARTIFACT_REGISTRY[artifact];
      const archView = viewFromArtifactType(entry.routeKey);
      patchParams({
        view: archView,
        artifact: entry.routeKey,
        req: null,
        node: null,
        role: null,
        test: null,
        risk: null,
        sel: null,
        selId: null,
        mode: null,
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
      const view = selectedArchitectureView ?? 'system';
      const artifact = artifactTypeFromView(view);
      const selKind = selectionKindForArchitectureView(view);
      patchParams({
        view,
        artifact,
        node: id,
        sel: id ? selKind : null,
        selId: id,
      });
    },
    [patchParams, selectedArchitectureView],
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

  const setSelectedTest = useCallback(
    (id: string | null) => {
      patchParams({
        view: null,
        artifact: 'test-plan',
        test: id,
        sel: id ? 'test' : null,
        selId: id,
      });
    },
    [patchParams],
  );

  const setSelectedRisk = useCallback(
    (id: string | null) => {
      patchParams({
        view: null,
        artifact: 'risk-register',
        risk: id,
        sel: id ? 'risk' : null,
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

  const setInspectorPanel = useCallback(
    (mode: InspectorPanelMode) => {
      patchParams({ panel: mode === 'context' ? null : mode });
    },
    [patchParams],
  );

  const focusVera = useCallback(() => {
    const keepArchView = architectureViewFromParam;
    patchParams({
      view: keepArchView,
      panel: 'vera',
    });
    requestAnimationFrame(() => {
      document.getElementById('vera-turn')?.focus();
    });
  }, [architectureViewFromParam, patchParams]);

  return {
    globalView,
    selectedArchitectureView,
    selectedArtifact,
    selectedRequirement,
    selectedArchNode,
    selectedComponentRole,
    selectedTest,
    selectedRisk,
    historyOpen,
    inspectorPanel,
    electricalMode,
    selection,
    setGlobalView,
    setArchitectureView,
    setElectricalMode,
    setSelectedArtifact,
    setSelectedRequirement,
    setSelectedArchNode,
    setSelectedComponentRole,
    setSelectedTest,
    setSelectedRisk,
    setInspectorSelection,
    setHistoryOpen,
    setInspectorPanel,
    focusVera,
    patchParams,
  };
}
