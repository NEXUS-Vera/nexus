import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Toaster } from 'sonner';
import type {
  ExecutionRun,
  ProjectBoardProjection,
  ProjectCurrentState,
  ProjectEvent,
  ProjectHistory,
} from '@nexus/contracts';
import {
  ApiClientError,
  getProject,
  getProjectBoard,
  getProjectHistory,
  listEvents,
  listExecutions,
  submitProjectTurn,
} from '../api/client';
import { selectArtifactByType } from '../artifacts';
import {
  resolveWorkspaceRenderer,
  shellMetaFor,
} from '../artifacts/renderers/registry';
import { ArtifactWorkspaceShell } from '../artifacts/shell/ArtifactWorkspaceShell';
import type { ArtifactRouteKey } from '../artifacts/types';
import { changeIndicatorFor } from '../artifacts/types';
import { AppHeader } from '../components/layout/AppHeader';
import { ContextInspector } from '../components/layout/ContextInspector';
import { WorkflowRail } from '../components/layout/WorkflowRail';
import { HistoryPanel } from '../components/feedback/HistoryPanel';
import type { VeraContextChip } from '../components/feedback/VeraPanel';
import { CommandPalette } from '../components/navigation/CommandPalette';
import { useTheme } from '../hooks/use-theme';
import { useWorkspaceUrl } from '../hooks/use-workspace-url';
import { themeColors } from '../lib/theme';
import { MindGraphWorkspace } from '../views/MindGraphWorkspace';
import { ProjectOverview } from '../views/ProjectOverview';
import { ARTIFACT_REGISTRY } from '../artifacts/registry';

async function loadOptional<T>(loader: () => Promise<T>): Promise<T | null> {
  try {
    return await loader();
  } catch (err) {
    if (err instanceof ApiClientError && (err.status === 404 || err.status === 501)) {
      return null;
    }
    return null;
  }
}

export function ProjectPage() {
  const { projectId = '' } = useParams();
  const { isDark, toggleDark } = useTheme();
  const t = themeColors(isDark);
  const url = useWorkspaceUrl();

  const [state, setState] = useState<ProjectCurrentState | null>(null);
  const [history, setHistory] = useState<ProjectHistory | null>(null);
  const [board, setBoard] = useState<ProjectBoardProjection | null>(null);
  const [events, setEvents] = useState<ProjectEvent[]>([]);
  const [executions, setExecutions] = useState<ExecutionRun[]>([]);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [regenerated, setRegenerated] = useState<string[]>([]);
  const [changed, setChanged] = useState<string[]>([]);
  const [affected, setAffected] = useState<string[]>([]);
  const [stale, setStale] = useState<string[]>([]);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [inspectorCollapsed, setInspectorCollapsed] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [showNextAction, setShowNextAction] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [project, hist, boardProjection, projectEvents, projectExecutions] =
          await Promise.all([
            getProject(projectId),
            getProjectHistory(projectId),
            loadOptional(() => getProjectBoard(projectId)),
            loadOptional(() => listEvents(projectId)),
            loadOptional(() => listExecutions(projectId)),
          ]);
        if (!cancelled) {
          setState(project);
          setHistory(hist);
          setBoard(boardProjection);
          setEvents(projectEvents ?? []);
          setExecutions(projectExecutions ?? []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiClientError ? err.message : 'Failed to load project');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const live = useMemo(() => {
    if (!state) return null;
    return {
      brief: selectArtifactByType(state.artifacts, 'project-brief'),
      requirements: selectArtifactByType(state.artifacts, 'requirement-set'),
      architecture: selectArtifactByType(state.artifacts, 'functional-architecture'),
      nextAction: selectArtifactByType(state.artifacts, 'next-action'),
      componentPlan: selectArtifactByType(state.artifacts, 'component-plan'),
    };
  }, [state]);

  const changeByType = useMemo(() => {
    const map: Record<string, string> = {};
    for (const type of [
      'project-brief',
      'requirement-set',
      'functional-architecture',
      'next-action',
      'component-plan',
    ]) {
      const version =
        live && type in live
          ? (live[type as keyof typeof live] as { artifactVersion: number } | undefined)
              ?.artifactVersion ?? 1
          : 1;
      map[type] = changeIndicatorFor(type, version, regenerated, changed, affected, stale);
    }
    return map;
  }, [affected, changed, live, regenerated, stale]);

  const architectureCoverage = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const node of live?.architecture?.content.nodes ?? []) {
      for (const reqId of node.satisfiesRequirementIds) {
        map[reqId] = [...(map[reqId] ?? []), node.name];
      }
    }
    return map;
  }, [live?.architecture]);

  async function refreshBoardSideChannels() {
    const [boardProjection, projectEvents, projectExecutions] = await Promise.all([
      loadOptional(() => getProjectBoard(projectId)),
      loadOptional(() => listEvents(projectId)),
      loadOptional(() => listExecutions(projectId)),
    ]);
    setBoard(boardProjection);
    setEvents(projectEvents ?? []);
    setExecutions(projectExecutions ?? []);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting || !message.trim() || !state) return;
    const ok = await submitTurnMessage(message.trim());
    if (ok) setMessage('');
  }

  async function submitTurnMessage(turnMessage: string): Promise<boolean> {
    if (submitting || !turnMessage.trim() || !state) return false;
    setSubmitting(true);
    setError(null);
    try {
      const result = await submitProjectTurn({
        projectId,
        message: turnMessage.trim(),
      });
      setState(result.currentState);
      setRegenerated(result.regeneratedArtifactTypes ?? []);
      setChanged(result.changedArtifactTypes ?? []);
      setAffected(result.impactAnalysis?.affected ?? []);
      setStale(result.impactAnalysis?.stale ?? []);
      setHistory(await getProjectHistory(projectId));
      await refreshBoardSideChannels();
      return true;
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Failed to submit turn');
      return false;
    } finally {
      setSubmitting(false);
    }
  }

  const focusVera = useCallback(() => {
    setInspectorCollapsed(false);
    url.focusVera();
  }, [url]);

  const veraContextChips = useMemo((): VeraContextChip[] => {
    const chips: VeraContextChip[] = [];
    const def = ARTIFACT_REGISTRY[url.selectedArtifact];
    chips.push({
      kind: 'artifact',
      label: def?.label ?? url.selectedArtifact,
    });
    const plan = live?.componentPlan;
    if (!plan) return chips;
    const roleId =
      url.selectedComponentRole ??
      (url.selection.kind === 'component-role' ? url.selection.id : null);
    if (roleId) {
      const role = plan.content.componentRoles.find(
        (r) => r.componentRoleId === roleId || r.displayId === roleId,
      );
      if (role) {
        chips.push({ kind: 'role', label: role.name });
      }
    }
    return chips;
  }, [live?.componentPlan, url.selectedArtifact, url.selectedComponentRole, url.selection]);

  if (loading) {
    return (
      <main className="page" aria-live="polite">
        <p>Loading project…</p>
      </main>
    );
  }

  if (!state || !live?.brief || !live.requirements || !live.architecture || !live.nextAction) {
    return (
      <main className="page">
        <p role="alert">{error ?? 'Project not found.'}</p>
        <Link to="/">Start a new project</Link>
      </main>
    );
  }

  function handleRequestAlternatives(roleId: string, suggestedPrompt: string) {
    url.setSelectedComponentRole(roleId);
    setMessage(suggestedPrompt);
    focusVera();
  }

  function renderRegisteredWorkspace(rendererKey: string) {
    const Renderer = resolveWorkspaceRenderer(rendererKey);
    const meta = shellMetaFor(rendererKey, state!, changeByType);
    return (
      <ArtifactWorkspaceShell
        title={meta.title}
        subtitle={meta.subtitle}
        version={meta.version}
        lifecycleStatus={meta.lifecycleStatus}
        evidenceStatus={meta.evidenceStatus}
        approvalStatus={meta.approvalStatus}
        changeIndicator={meta.changeIndicator}
        isDark={isDark}
        testId={meta.testId}
      >
        <Renderer
          projectId={projectId}
          rendererKey={rendererKey}
          state={state!}
          isDark={isDark}
          changeIndicator={meta.changeIndicator}
          selectedRequirementId={url.selectedRequirement}
          selectedNodeId={url.selectedArchNode}
          selectedRoleId={url.selectedComponentRole}
          onSelectRequirement={url.setSelectedRequirement}
          onSelectNode={url.setSelectedArchNode}
          onSelectRole={url.setSelectedComponentRole}
          onSelectItem={url.setInspectorSelection}
          architectureNodeIdsByRequirement={architectureCoverage}
          nextActionTitle={live!.nextAction!.content.title}
          turnBusy={submitting}
          onSubmitTurn={submitTurnMessage}
          onRequestAlternatives={handleRequestAlternatives}
          onAskVera={focusVera}
          onCommandResult={() => {
            void refreshBoardSideChannels();
            void getProject(projectId).then(setState).catch(() => undefined);
          }}
        />
      </ArtifactWorkspaceShell>
    );
  }

  function renderCenter() {
    if (url.globalView === 'overview') {
      return (
        <ProjectOverview
          state={state!}
          board={board}
          history={history}
          executions={executions}
          isDark={isDark}
          onNavigate={(key) => {
            setShowNextAction(false);
            url.setSelectedArtifact(key);
          }}
          onOpenNextAction={() => {
            setShowNextAction(true);
            url.setGlobalView('workspace');
            url.setInspectorSelection({ kind: 'next-action' });
          }}
          onOpenHistory={() => url.setHistoryOpen(true)}
        />
      );
    }
    if (url.globalView === 'mind-graph') {
      return (
        <MindGraphWorkspace
          state={state!}
          isDark={isDark}
          onNavigate={(key) => {
            setShowNextAction(false);
            url.setSelectedArtifact(key);
          }}
        />
      );
    }
    if (showNextAction) {
      return renderRegisteredWorkspace('next-action');
    }
    return renderRegisteredWorkspace(url.selectedArtifact);
  }

  function selectArtifact(key: ArtifactRouteKey) {
    setShowNextAction(false);
    url.setSelectedArtifact(key);
  }

  return (
    <div
      data-testid="figma-shell"
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: t.bg,
        fontFamily: 'var(--nx-font)',
        overflow: 'hidden',
        color: t.text,
      }}
    >
      <Toaster position="bottom-right" richColors />
      <AppHeader
        projectTitle={state.project.title}
        projectDomain={state.project.domain}
        projectId={state.project.projectId}
        stateVersion={state.project.currentStateVersion}
        globalView={url.globalView}
        onGlobalViewChange={(view) => {
          setShowNextAction(false);
          url.setGlobalView(view);
        }}
        isDark={isDark}
        onToggleDark={toggleDark}
        onOpenCommandPalette={() => setCommandPaletteOpen(true)}
        onToggleHistory={() => url.setHistoryOpen(!url.historyOpen)}
        historyOpen={url.historyOpen}
      />

      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex' }}>
        <PanelGroup direction="horizontal" style={{ flex: 1, overflow: 'hidden' }}>
          <Panel
            defaultSize={railCollapsed ? 5 : 16}
            minSize={railCollapsed ? 4 : 13}
            maxSize={railCollapsed ? 6 : 22}
          >
            <WorkflowRail
              selectedArtifact={url.selectedArtifact}
              onSelectArtifact={selectArtifact}
              collapsed={railCollapsed}
              onCollapsedChange={setRailCollapsed}
              isDark={isDark}
              artifacts={state.artifacts}
              nextAction={live.nextAction}
              changeByType={changeByType}
              onOpenNextAction={() => {
                setShowNextAction(true);
                url.setGlobalView('workspace');
                url.setInspectorSelection({ kind: 'next-action' });
              }}
              onOpenHistory={() => url.setHistoryOpen(true)}
            />
          </Panel>

          <PanelResizeHandle>
            <div
              style={{
                width: 4,
                height: '100%',
                background: t.border,
                cursor: 'col-resize',
              }}
            />
          </PanelResizeHandle>

          <Panel defaultSize={62} minSize={40}>
            <div style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                {renderCenter()}
              </div>
              {url.historyOpen && history ? (
                <HistoryPanel
                  history={history}
                  isDark={isDark}
                  onClose={() => url.setHistoryOpen(false)}
                  onSelectRevision={url.setInspectorSelection}
                />
              ) : null}
            </div>
          </Panel>

          <PanelResizeHandle>
            <div
              style={{
                width: 4,
                height: '100%',
                background: t.border,
                cursor: 'col-resize',
              }}
            />
          </PanelResizeHandle>

          <Panel
            defaultSize={inspectorCollapsed ? 4 : 22}
            minSize={inspectorCollapsed ? 3 : 16}
            maxSize={inspectorCollapsed ? 5 : 30}
          >
            <ContextInspector
              collapsed={inspectorCollapsed}
              onCollapsedChange={setInspectorCollapsed}
              isDark={isDark}
              activeArtifact={url.selectedArtifact}
              selection={url.selection}
              state={state}
              board={board}
              events={events}
              executions={executions}
              history={history}
              changedArtifactTypes={changed}
              regeneratedArtifactTypes={regenerated}
              onFocusVera={focusVera}
              inspectorPanel={url.inspectorPanel}
              onInspectorPanelChange={url.setInspectorPanel}
              veraMessageDraft={message}
              onVeraMessageChange={setMessage}
              onVeraSubmit={onSubmit}
              veraSubmitting={submitting}
              veraError={error}
              veraContextChips={veraContextChips}
            />
          </Panel>
        </PanelGroup>
      </div>

      <CommandPalette
        open={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        isDark={isDark}
        state={state}
        onSetGlobalView={url.setGlobalView}
        onSelectArtifact={selectArtifact}
        onSelectRequirement={url.setSelectedRequirement}
        onOpenNextAction={() => {
          setShowNextAction(true);
          url.setGlobalView('workspace');
          url.setInspectorSelection({ kind: 'next-action' });
        }}
        onOpenHistory={() => url.setHistoryOpen(true)}
        onFocusVera={focusVera}
      />
    </div>
  );
}
