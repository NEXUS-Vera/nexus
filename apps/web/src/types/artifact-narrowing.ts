/**
 * Compile-time narrowing checks for generated Artifact unions.
 * This file is typechecked by `pnpm --filter @nexus/web typecheck`.
 */
import type { Artifact } from '@nexus/contracts';

export function assertRequirementNarrowing(artifact: Artifact): number {
  if (artifact.artifactType === 'requirement-set') {
    return artifact.content.requirements.length;
  }
  return 0;
}

export function assertBriefNarrowing(artifact: Artifact): string {
  if (artifact.artifactType === 'project-brief') {
    return artifact.content.goal;
  }
  return '';
}

export function rejectExtraProperty(artifact: Artifact): string {
  if (artifact.artifactType === 'next-action') {
    // Undeclared fields must not exist on narrowed artifact variants.
    // @ts-expect-error intentionally invalid extra property access
    return artifact.notARealField;
  }
  return '';
}
