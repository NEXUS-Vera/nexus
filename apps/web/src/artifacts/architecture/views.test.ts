import { describe, expect, it } from 'vitest';
import {
  ARCHITECTURE_VIEW_REGISTRY,
  artifactTypeFromView,
  isArchitectureViewId,
  viewFromArtifactType,
} from './views';

describe('architecture view registry', () => {
  it('maps views to artifact types bi-directionally', () => {
    expect(artifactTypeFromView('system')).toBe('functional-architecture');
    expect(artifactTypeFromView('electrical')).toBe('electrical-architecture');
    expect(artifactTypeFromView('physical')).toBe('physical-architecture');
    expect(viewFromArtifactType('functional-architecture')).toBe('system');
    expect(viewFromArtifactType('electrical-architecture')).toBe('electrical');
    expect(viewFromArtifactType('physical-architecture')).toBe('physical');
    expect(viewFromArtifactType('component-plan')).toBeNull();
  });

  it('exposes labels and descriptions for each view', () => {
    expect(Object.keys(ARCHITECTURE_VIEW_REGISTRY)).toEqual(['system', 'electrical', 'physical']);
    expect(ARCHITECTURE_VIEW_REGISTRY.system.label).toBe('System');
    expect(ARCHITECTURE_VIEW_REGISTRY.electrical.artifactType).toBe('electrical-architecture');
    expect(ARCHITECTURE_VIEW_REGISTRY.physical.description.length).toBeGreaterThan(10);
  });

  it('validates architecture view ids', () => {
    expect(isArchitectureViewId('system')).toBe(true);
    expect(isArchitectureViewId('workspace')).toBe(false);
    expect(isArchitectureViewId(null)).toBe(false);
  });
});
