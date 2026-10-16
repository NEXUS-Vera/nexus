export type ArchitectureViewId = 'system' | 'electrical' | 'physical';

export type ArchitectureArtifactType =
  | 'functional-architecture'
  | 'electrical-architecture'
  | 'physical-architecture';

export const ARCHITECTURE_VIEW_REGISTRY: Record<
  ArchitectureViewId,
  {
    id: ArchitectureViewId;
    label: string;
    artifactType: ArchitectureArtifactType;
    description: string;
  }
> = {
  system: {
    id: 'system',
    label: 'System',
    artifactType: 'functional-architecture',
    description: 'Functional blocks, responsibilities, and requirement coverage.',
  },
  electrical: {
    id: 'electrical',
    label: 'Electrical',
    artifactType: 'electrical-architecture',
    description: 'Implementation nodes, interfaces, connections, and power domains.',
  },
  physical: {
    id: 'physical',
    label: 'Physical',
    artifactType: 'physical-architecture',
    description: 'Assemblies, zones, placement, and physical relationships.',
  },
};

export const ARCHITECTURE_VIEW_ORDER: ArchitectureViewId[] = [
  'system',
  'electrical',
  'physical',
];

export function isArchitectureViewId(value: string | null | undefined): value is ArchitectureViewId {
  return value === 'system' || value === 'electrical' || value === 'physical';
}

export function isArchitectureArtifactType(
  value: string | null | undefined,
): value is ArchitectureArtifactType {
  return (
    value === 'functional-architecture' ||
    value === 'electrical-architecture' ||
    value === 'physical-architecture'
  );
}

export function viewFromArtifactType(
  artifactType: string | null | undefined,
): ArchitectureViewId | null {
  if (artifactType === 'functional-architecture') return 'system';
  if (artifactType === 'electrical-architecture') return 'electrical';
  if (artifactType === 'physical-architecture') return 'physical';
  return null;
}

export function artifactTypeFromView(view: ArchitectureViewId): ArchitectureArtifactType {
  return ARCHITECTURE_VIEW_REGISTRY[view].artifactType;
}

/** True when the workflow-rail Architecture item should appear selected. */
export function isArchitectureNavSelected(artifact: string | null | undefined): boolean {
  return isArchitectureArtifactType(artifact);
}
