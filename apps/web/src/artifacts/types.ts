/** Frontend artifact route keys for the board workspace. */
export type ArtifactRouteKey =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'component-plan'
  | 'firmware-scaffold'
  | 'analysis-notebook'
  | 'test-plan'
  | 'risk-register';

export type WorkflowPhase = 'DEFINE' | 'DESIGN' | 'BUILD' | 'VERIFY';

export type GlobalView = 'overview' | 'workspace' | 'mind-graph';

export type ArtifactAvailability = 'live' | 'proof' | 'placeholder';

/** Canonical live / proof artifact types recognized by the board UI. */
export type LiveArtifactType =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'firmware';

export type ChangeIndicator = 'Updated' | 'Regenerated' | 'Unchanged' | 'Affected' | 'Stale' | 'Current';

export function changeIndicatorFor(
  artifactType: string,
  version: number,
  regenerated: string[],
  changed: string[],
  affected: string[] = [],
  stale: string[] = [],
): ChangeIndicator {
  if (regenerated.includes(artifactType)) return 'Regenerated';
  if (changed.includes(artifactType)) return 'Updated';
  if (affected.includes(artifactType)) return 'Affected';
  if (stale.includes(artifactType)) return 'Stale';
  if (version > 1) return 'Updated';
  return 'Unchanged';
}
