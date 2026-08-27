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

vi.mock('@monaco-editor/react', () => ({
  default: () => <div data-testid="firmware-monaco-editor" />,
}));

const state = fixture as unknown as ProjectCurrentState;

describe('workspace renderer registry', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.includes('/workspace/files')
          ? {
              files: [],
              binding: {
                schemaVersion: '1.0.0',
                projectId: state.project.projectId,
                artifactId: 'art_firmware',
                artifactType: 'firmware',
                workspaceId: 'ws_firmware',
                baseArtifactVersion: 1,
                baseProjectStateVersion: 1,
                capabilities: { filesystem: true, execution: true },
                filesystemEnabled: true,
              },
              draft: { draftVersion: 1 },
            }
          : {
              binding: {
                schemaVersion: '1.0.0',
                projectId: state.project.projectId,
                artifactId: 'art_firmware',
                artifactType: 'firmware',
                workspaceId: 'ws_firmware',
                baseArtifactVersion: 1,
                baseProjectStateVersion: 1,
                capabilities: { filesystem: true, execution: true },
                filesystemEnabled: true,
              },
              draft: { draftVersion: 1 },
            };
        return {
          ok: true,
          status: 200,
          json: async () => body,
          text: async () => JSON.stringify(body),
        };
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('registers component-plan, firmware, and core live renderers by key', () => {
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
        'analysis',
        'firmware',
        'test-plan',
        'risk-register',
      ]),
    );
    expect(keys).toHaveLength(11);

    const shuffled = [...keys].sort().reverse();
    for (const key of shuffled) {
      expect(isWorkspaceRendererKey(key)).toBe(true);
      expect(getWorkspaceRenderer(key)).toBe(
        WORKSPACE_RENDERER_REGISTRY[key as keyof typeof WORKSPACE_RENDERER_REGISTRY],
      );
    }
  });

  it('does not let registration order affect lookup', () => {
    const brief = getWorkspaceRenderer('project-brief');
    const components = getWorkspaceRenderer('component-plan');
    const firmware = getWorkspaceRenderer('firmware');
    expect(brief).toBeDefined();
    expect(components).toBeDefined();
    expect(firmware).toBeDefined();
    expect(brief).not.toBe(components);
    expect(getWorkspaceRenderer('project-brief')).toBe(brief);
  });

  it('returns undefined for unsupported keys and resolves safely to UnavailableWorkspace', () => {
    expect(getWorkspaceRenderer('not-a-real-artifact')).toBeUndefined();
    expect(resolveWorkspaceRenderer('not-a-real-artifact')).toBe(UnavailableWorkspace);
  });

  it('renders unavailable workspaces honestly when artifact is missing', () => {
    render(
      <UnavailableWorkspace
        rendererKey="test-plan"
        isDark={false}
        reason="Test Plan artifact is missing from current state."
      />,
    );
    expect(screen.getByTestId('unavailable-workspace')).toHaveTextContent(/Test Plan/i);
    expect(screen.getByTestId('unavailable-workspace')).toHaveTextContent(/missing from current state/i);
  });

  it('renders firmware through the registry', async () => {
    const Renderer = getWorkspaceRenderer('firmware');
    expect(Renderer).toBeDefined();
    if (!Renderer) {
      throw new Error('expected firmware renderer');
    }
    render(
      <Renderer
        projectId={state.project.projectId}
        rendererKey="firmware"
        state={state}
        isDark={false}
      />,
    );
    await vi.waitFor(() => {
      expect(screen.getByTestId('firmware-workspace')).toBeInTheDocument();
    });
  });

  it('marks firmware as live in the artifact registry', async () => {
    const { ARTIFACT_REGISTRY } = await import('../registry');
    expect(ARTIFACT_REGISTRY.firmware.availability).toBe('live');
    expect(ARTIFACT_REGISTRY.firmware.artifactType).toBe('firmware');
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
  });
});
