import type { ComponentType } from 'react';
import type { Artifact, ArtifactCommandResult, ProjectCurrentState } from '@nexus/contracts';
import type { InspectorSelection } from '../../lib/inspector-selection';
import { themeColors } from '../../lib/theme';
import { PlaceholderWorkspace } from '../../components/layout/PlaceholderWorkspace';
import { ArchitectureWorkspace } from '../architecture/workspace';
import { ComponentPlanWorkspace } from '../component-plan/workspace';
import { NextActionWorkspace } from '../next-action/workspace';
import { ProjectBriefWorkspace } from '../project-brief/workspace';
import { RequirementsWorkspace } from '../requirements/workspace';
import { ARTIFACT_REGISTRY, isArtifactRouteKey } from '../registry';
import { selectArtifactByType } from '../../artifacts';
import type { ArtifactRouteKey } from '../types';

/** Keys that have a dedicated React workspace renderer (separate from ARTIFACT_REGISTRY). */
export type WorkspaceRendererKey =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan';

export type WorkspaceRenderProps = {
  projectId: string;
  rendererKey: WorkspaceRendererKey | string;
  state: ProjectCurrentState;
  isDark: boolean;
  changeIndicator?: string;
  selectedRequirementId?: string | null;
  selectedNodeId?: string | null;
  selectedRoleId?: string | null;
  onSelectRequirement?: (id: string) => void;
  onSelectNode?: (id: string) => void;
  onSelectRole?: (id: string) => void;
  onSelectItem?: (selection: InspectorSelection) => void;
  architectureNodeIdsByRequirement?: Record<string, string[]>;
  onCommandResult?: (result: ArtifactCommandResult) => void;
  onSubmitTurn?: (message: string) => Promise<boolean>;
  turnBusy?: boolean;
  nextActionTitle?: string;
};

function ProjectBriefRenderer(props: WorkspaceRenderProps) {
  const artifact = selectArtifactByType(props.state.artifacts, 'project-brief');
  if (!artifact || !props.onSelectItem) {
    return (
      <UnavailableWorkspace
        rendererKey="project-brief"
        isDark={props.isDark}
        reason="Project brief artifact is missing from current state."
      />
    );
  }
  return (
    <ProjectBriefWorkspace
      artifact={artifact}
      isDark={props.isDark}
      onSelectItem={props.onSelectItem}
    />
  );
}

function RequirementsRenderer(props: WorkspaceRenderProps) {
  const artifact = selectArtifactByType(props.state.artifacts, 'requirement-set');
  if (!artifact || !props.onSelectRequirement) {
    return (
      <UnavailableWorkspace
        rendererKey="requirement-set"
        isDark={props.isDark}
        reason="Requirement set artifact is missing from current state."
      />
    );
  }
  return (
    <RequirementsWorkspace
      artifact={artifact}
      isDark={props.isDark}
      selectedRequirementId={props.selectedRequirementId ?? null}
      onSelectRequirement={props.onSelectRequirement}
      architectureNodeIdsByRequirement={props.architectureNodeIdsByRequirement}
    />
  );
}

function ArchitectureRenderer(props: WorkspaceRenderProps) {
  const artifact = selectArtifactByType(props.state.artifacts, 'functional-architecture');
  if (!artifact || !props.onSelectNode) {
    return (
      <UnavailableWorkspace
        rendererKey="functional-architecture"
        isDark={props.isDark}
        reason="Functional architecture artifact is missing from current state."
      />
    );
  }
  return (
    <ArchitectureWorkspace
      artifact={artifact}
      isDark={props.isDark}
      selectedNodeId={props.selectedNodeId ?? null}
      onSelectNode={props.onSelectNode}
    />
  );
}

function NextActionRenderer(props: WorkspaceRenderProps) {
  const artifact = selectArtifactByType(props.state.artifacts, 'next-action');
  if (!artifact) {
    return (
      <UnavailableWorkspace
        rendererKey="next-action"
        isDark={props.isDark}
        reason="Next action artifact is missing from current state."
      />
    );
  }
  return <NextActionWorkspace artifact={artifact} isDark={props.isDark} />;
}

function ComponentPlanRenderer(props: WorkspaceRenderProps) {
  const artifact = selectArtifactByType(props.state.artifacts, 'component-plan') as
    | Extract<Artifact, { artifactType: 'component-plan' }>
    | undefined;
  return (
    <ComponentPlanWorkspace
      projectId={props.projectId}
      artifact={artifact}
      isDark={props.isDark}
      selectedRoleId={props.selectedRoleId ?? null}
      onSelectRole={props.onSelectRole}
      onSubmitTurn={props.onSubmitTurn}
      turnBusy={props.turnBusy}
      onCommandResult={props.onCommandResult}
    />
  );
}

/**
 * Frontend workspace renderer registry.
 * Lookup is by artifactType / routeKey — never by array position.
 */
export const WORKSPACE_RENDERER_REGISTRY: Record<
  WorkspaceRendererKey,
  ComponentType<WorkspaceRenderProps>
> = {
  'project-brief': ProjectBriefRenderer,
  'requirement-set': RequirementsRenderer,
  'functional-architecture': ArchitectureRenderer,
  'next-action': NextActionRenderer,
  'component-plan': ComponentPlanRenderer,
};

export function isWorkspaceRendererKey(value: string): value is WorkspaceRendererKey {
  return Object.prototype.hasOwnProperty.call(WORKSPACE_RENDERER_REGISTRY, value);
}

export function getWorkspaceRenderer(
  key: string,
): ComponentType<WorkspaceRenderProps> | undefined {
  if (!isWorkspaceRendererKey(key)) return undefined;
  return WORKSPACE_RENDERER_REGISTRY[key];
}

export function resolveWorkspaceRenderer(key: string): ComponentType<WorkspaceRenderProps> {
  return getWorkspaceRenderer(key) ?? UnavailableWorkspace;
}

export function UnavailableWorkspace({
  rendererKey,
  isDark,
  reason,
  nextActionTitle,
}: {
  rendererKey?: string;
  isDark: boolean;
  reason?: string;
  nextActionTitle?: string;
} & Partial<WorkspaceRenderProps>) {
  const key = rendererKey;
  const def = key && isArtifactRouteKey(key) ? ARTIFACT_REGISTRY[key as ArtifactRouteKey] : null;
  const t = themeColors(isDark);

  if (def && def.availability === 'placeholder') {
    return (
      <PlaceholderWorkspace
        title={def.placeholderTitle}
        body={def.placeholderBody}
        prerequisites={def.dependencyLabels}
        nextActionTitle={nextActionTitle}
        isDark={isDark}
      />
    );
  }

  return (
    <div
      data-testid="unavailable-workspace"
      style={{
        flex: 1,
        overflow: 'auto',
        padding: 24,
        background: t.bg,
      }}
    >
      <div
        style={{
          maxWidth: 640,
          margin: '40px auto',
          padding: 24,
          borderRadius: 8,
          border: `1px dashed ${t.border}`,
          background: t.surface,
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.08em',
            color: t.textMuted,
            textTransform: 'uppercase',
          }}
        >
          Unavailable workspace
        </p>
        <h2 style={{ margin: '8px 0 0', fontSize: 18, color: t.text }}>
          {def?.label ?? key ?? 'Unknown artifact'}
        </h2>
        <p style={{ margin: '10px 0 0', fontSize: 13, color: t.textSec, lineHeight: 1.5 }}>
          {reason ??
            'No frontend renderer is registered for this artifact. The board will not invent a fake workspace.'}
        </p>
      </div>
    </div>
  );
}

export function shellMetaFor(
  key: string,
  state: ProjectCurrentState,
  changeByType: Record<string, string>,
): {
  title: string;
  subtitle?: string;
  version?: number;
  lifecycleStatus?: string;
  evidenceStatus?: string;
  approvalStatus?: string;
  changeIndicator?: string;
  testId?: string;
} {
  if (key === 'next-action') {
    const artifact = selectArtifactByType(state.artifacts, 'next-action');
    return {
      title: 'Next Action',
      subtitle: 'Global recommended action for this project',
      version: artifact?.artifactVersion,
      lifecycleStatus: artifact?.lifecycleStatus,
      evidenceStatus: artifact?.evidenceStatus,
      approvalStatus: artifact?.approvalStatus,
      changeIndicator: changeByType['next-action'],
      testId: 'workspace-next-action-shell',
    };
  }

  if (isArtifactRouteKey(key)) {
    const def = ARTIFACT_REGISTRY[key];
    const liveType = def.artifactType;
    const artifact =
      liveType == null
        ? undefined
        : state.artifacts.find((a) => a.artifactType === liveType);

    const testIds: Partial<Record<ArtifactRouteKey, string>> = {
      'project-brief': 'workspace-project-brief-shell',
      'requirement-set': 'workspace-requirements-shell',
      'functional-architecture': 'workspace-architecture-shell',
      'component-plan': 'workspace-component-plan-shell',
    };

    let subtitle: string | undefined;
    if (key === 'project-brief') {
      subtitle = 'Read-only live artifact. Request edits through Vera.';
    } else if (key === 'requirement-set' && artifact?.artifactType === 'requirement-set') {
      subtitle = `${artifact.content.requirements.length} requirements`;
    } else if (
      key === 'functional-architecture' &&
      artifact?.artifactType === 'functional-architecture'
    ) {
      subtitle = `Functional maturity: ${artifact.content.architectureMaturity}`;
    } else if (
      key === 'component-plan' &&
      artifact?.artifactType === 'component-plan'
    ) {
      const roles = artifact.content.componentRoles.length;
      const candidates = artifact.content.candidates.length;
      subtitle = `${artifact.content.maturity} · ${roles} roles · ${candidates} candidates`;
    } else if (key === 'component-plan') {
      subtitle = 'Component comparison workspace';
    } else if (def.availability === 'placeholder') {
      subtitle = 'Future artifact — not produced yet';
    }

    return {
      title: def.label,
      subtitle,
      version: artifact?.artifactVersion,
      lifecycleStatus:
        artifact?.lifecycleStatus ??
        (def.availability === 'placeholder' ? 'unavailable' : undefined),
      evidenceStatus: artifact?.evidenceStatus,
      approvalStatus: artifact?.approvalStatus,
      changeIndicator: liveType ? changeByType[liveType] : undefined,
      testId: testIds[key],
    };
  }

  return {
    title: key || 'Unknown',
    lifecycleStatus: 'unavailable',
    testId: 'unavailable-workspace-shell',
  };
}
