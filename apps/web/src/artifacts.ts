import type { Artifact } from '@nexus/contracts';

export function selectArtifactByType<T extends Artifact['artifactType']>(
  artifacts: Artifact[],
  artifactType: T,
): Extract<Artifact, { artifactType: T }> | undefined {
  return artifacts.find(
    (artifact): artifact is Extract<Artifact, { artifactType: T }> =>
      artifact.artifactType === artifactType,
  );
}
