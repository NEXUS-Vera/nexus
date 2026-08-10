import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from '../../../../../packages/contracts/examples/valid/project-initialization-result/project-initialization-result.json';
import type { ProjectCurrentState } from '@nexus/contracts';
import {
  WORKSPACE_RENDERER_REGISTRY,
  getWorkspaceRenderer,
  isWorkspaceRendererKey,
  resolveWorkspaceRenderer,
  UnavailableWorkspace,
} from './registry';

const state = fixture as unknown as ProjectCurrentState;

describe('workspace renderer registry', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        text: async () => '',
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('registers component-plan and core live renderers by key, not position', () => {
    const keys = Object.keys(WORKSPACE_RENDERER_REGISTRY);
    expect(keys).toEqual(
      expect.arrayContaining([
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'electrical-architecture',
        'physical-architecture',
        'next-action',
        'component-plan',
      ]),
    );
    expect(keys).toHaveLength(7);

    const shuffled = [...keys].sort().reverse();
    for (const key of shuffled) {
      expect(isWorkspaceRendererKey(key)).toBe(true);
      expect(getWorkspaceRenderer(key)).toBe(WORKSPACE_RENDERER_REGISTRY[key as keyof typeof WORKSPACE_RENDERER_REGISTRY]);
    }
  });

  it('does not let registration order affect lookup', () => {
    const brief = getWorkspaceRenderer('project-brief');
    const components = getWorkspaceRenderer('component-plan');
    expect(brief).toBeDefined();
    expect(components).toBeDefined();
    expect(brief).not.toBe(components);
    expect(getWorkspaceRenderer('project-brief')).toBe(brief);
  });

  it('returns undefined for unsupported keys and resolves safely to UnavailableWorkspace', () => {
    expect(getWorkspaceRenderer('firmware-scaffold')).toBeUndefined();
    expect(getWorkspaceRenderer('not-a-real-artifact')).toBeUndefined();
    expect(resolveWorkspaceRenderer('firmware-scaffold')).toBe(UnavailableWorkspace);
  });

  it('renders unsupported workspace honestly', () => {
    render(
      <UnavailableWorkspace rendererKey="firmware-scaffold" isDark={false} />,
    );
    expect(screen.getByTestId('artifact-placeholder')).toHaveTextContent(
      /Firmware scaffold unavailable/i,
    );
  });

  it('renders component-plan through the registry', async () => {
    const Renderer = getWorkspaceRenderer('component-plan');
    expect(Renderer).toBeDefined();
    if (!Renderer) {
      throw new Error('expected component-plan renderer');
    }
    render(
      <Renderer
        projectId={state.project.projectId}
        rendererKey="component-plan"
        state={state}
        isDark={false}
      />,
    );
    expect(screen.getByTestId('workspace-component-plan')).toBeInTheDocument();
    expect(screen.getByTestId('component-plan-summary')).toBeInTheDocument();
    expect(screen.getByTestId('component-plan-role-list')).toBeInTheDocument();
    await vi.waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });
  });

  it('marks component-plan as live in the artifact registry', async () => {
    const { ARTIFACT_REGISTRY } = await import('../registry');
    expect(ARTIFACT_REGISTRY['component-plan'].availability).toBe('live');
  });
});
