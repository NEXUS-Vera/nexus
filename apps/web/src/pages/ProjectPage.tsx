import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Toaster } from 'sonner';
import type { ProjectCurrentState, ProjectHistory } from '@nexus/contracts';
import {
  ApiClientError,
  getProject,
  getProjectHistory,
  submitProjectTurn,
} from '../api/client';
import { selectArtifactByType } from '../artifacts';
import { ArchitectureWorkspace } from '../artifacts/architecture/workspace';
import { FutureArtifactPlaceholder } from '../artifacts/placeholders';
import { NextActionWorkspace } from '../artifacts/next-action/workspace';
import { ProjectBriefWorkspace } from '../artifacts/project-brief/workspace';
import { RequirementsWorkspace } from '../artifacts/requirements/workspace';
import type { ArtifactRouteKey } from '../artifacts/types';
import { changeIndicatorFor } from '../artifacts/types';
import { AppHeader } from '../components/layout/AppHeader';
import { ContextInspector } from '../components/layout/ContextInspector';
import { WorkflowRail } from '../components/layout/WorkflowRail';
import { HistoryPanel } from '../components/feedback/HistoryPanel';
import { VeraPanel } from '../components/feedback/VeraPanel';
import { CommandPalette } from '../components/navigation/CommandPalette';
import { useTheme } from '../hooks/use-theme';
import { useWorkspaceUrl } from '../hooks/use-workspace-url';
import { themeColors } from '../lib/theme';
import { MindGraphWorkspace } from '../views/MindGraphWorkspace';
import { ProjectOverview } from '../views/ProjectOverview';

export function ProjectPage() {
  const { projectId = '' } = useParams();
  const { isDark, toggleDark } = useTheme();
  const t = themeColors(isDark);
  const url = useWorkspaceUrl();

  const [state, setState] = useState<ProjectCurrentState | null>(null);
  const [history, setHistory] = useState<ProjectHistory | null>(null);
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
        const [project, hist] = await Promise.all([
          getProject(projectId),
          getProjectHistory(projectId),
        ]);
        if (!cancelled) {
          setState(project);
          setHistory(hist);
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
    };
  }, [state]);

  const changeByType = useMemo(() => {
    const map: Record<string, string> = {};
    for (const type of ['project-brief', 'requirement-set', 'functional-architecture', 'next-action']) {
      const version =
        live && type in live
          ? (live[type as keyof typeof live] as { artifactVersion: number } | undefined)?.artifactVersion ?? 1
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

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting || !message.trim() || !state) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await submitProjectTurn({
        projectId,
        message: message.trim(),
      });
      setState(result.currentState);
      setRegenerated(result.regeneratedArtifactTypes ?? []);
      setChanged(result.changedArtifactTypes ?? []);
      setAffected(result.impactAnalysis?.affected ?? []);
      setStale(result.impactAnalysis?.stale ?? []);
      setMessage('');
      setHistory(await getProjectHistory(projectId));
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Failed to submit turn');
    } finally {
      setSubmitting(false);
    }
  }

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

  const openQuestions = (state.openQuestions ?? []).filter((q) => q.status === 'open');

  function renderCenter() {
    if (url.globalView === 'overview') {
      return (
        <ProjectOverview
          state={state!}
          history={history}
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
      return (
        <NextActionWorkspace
          artifact={live!.nextAction!}
          changeIndicator={changeByType['next-action']}
          isDark={isDark}
        />
      );
    }

    const key = url.selectedArtifact;
    if (key === 'project-brief') {
      return (
        <ProjectBriefWorkspace
          artifact={live!.brief!}
          changeIndicator={changeByType['project-brief']}
          isDark={isDark}
          onSelectItem={url.setInspectorSelection}
        />
      );
    }
    if (key === 'requirement-set') {
      return (
        <RequirementsWorkspace
          artifact={live!.requirements!}
          changeIndicator={changeByType['requirement-set']}
          isDark={isDark}
          selectedRequirementId={url.selectedRequirement}
          onSelectRequirement={(id) => {
            url.setSelectedRequirement(id);
          }}
          architectureNodeIdsByRequirement={architectureCoverage}
        />
      );
    }
    if (key === 'functional-architecture') {
      return (
        <ArchitectureWorkspace
          artifact={live!.architecture!}
          changeIndicator={changeByType['functional-architecture']}
          isDark={isDark}
          selectedNodeId={url.selectedArchNode}
          onSelectNode={(id) => url.setSelectedArchNode(id)}
        />
      );
    }
    if (
      key === 'component-plan' ||
      key === 'firmware-scaffold' ||
      key === 'analysis-notebook' ||
      key === 'test-plan' ||
      key === 'risk-register'
    ) {
      return (
        <FutureArtifactPlaceholder
          routeKey={key}
          isDark={isDark}
          nextActionTitle={live!.nextAction!.content.title}
        />
      );
    }
    return null;
  }

  function selectArtifact(key: ArtifactRouteKey) {
    setShowNextAction(false);
    url.setSelectedArtifact(key);
  }

  return (
    <div
      data-testid="figma-shell"
      style={{
        height: '100vh',
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

      <div style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
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
              <VeraPanel
                message={message}
                onMessageChange={setMessage}
                onSubmit={onSubmit}
                submitting={submitting}
                veraMessage={state.veraResponse.userFacingMessage}
                error={error}
                openQuestions={openQuestions}
                isDark={isDark}
              />
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
              changedArtifactTypes={changed}
              regeneratedArtifactTypes={regenerated}
              onFocusVera={url.focusVera}
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
        onFocusVera={url.focusVera}
      />
    </div>
  );
}
