import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import fixture from '../../../packages/contracts/examples/valid/project-initialization-result/project-initialization-result.json';
import { ARTIFACT_ORDER, ARTIFACT_REGISTRY } from './artifacts/registry';

function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

function historyPayload(projectId: string) {
  return {
    schemaVersion: '1.0.0',
    projectId,
    turns: [],
    workflowRuns: [],
    artifactRevisions: [],
    veraResponses: [],
  };
}

describe('Nexus web routing and project workspace', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders new project screen and example prompts', async () => {
    const user = userEvent.setup();
    renderApp();
    expect(screen.getByText(/Start a new embedded project/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Wearable tremor monitor/i }));
    expect((screen.getByLabelText(/Project idea/i) as HTMLTextAreaElement).value).toContain(
      'wrist-worn device',
    );
  });

  it('navigates to project route after successful initialization', async () => {
    const user = userEvent.setup();
    const projectId = (fixture as { project: { projectId: string } }).project.projectId;
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (String(url).includes('/initialize')) {
        return { ok: true, status: 200, text: async () => JSON.stringify(fixture) };
      }
      if (String(url).includes('/history')) {
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify(historyPayload(projectId)),
        };
      }
      return { ok: true, status: 200, text: async () => JSON.stringify(fixture) };
    });
    vi.stubGlobal('fetch', fetchMock);
    renderApp();
    await user.click(screen.getByRole('button', { name: /Wearable tremor monitor/i }));
    await user.click(screen.getByRole('button', { name: /Create project/i }));
    await waitFor(() => {
      expect(screen.getByText(new RegExp(projectId))).toBeInTheDocument();
    });
    expect(screen.getByTestId('figma-shell')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Vera' })).toBeInTheDocument();
    expect(screen.getByText(/Project Brief · v1/i)).toBeInTheDocument();
  });

  it('loads a persisted project from the project route and opens history', async () => {
    const projectId = (fixture as { project: { projectId: string } }).project.projectId;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (url: string) => {
        if (String(url).includes('/history')) {
          return {
            ok: true,
            status: 200,
            text: async () =>
              JSON.stringify({
                schemaVersion: '1.0.0',
                projectId,
                turns: [{ turnId: 'turn_x', timestamp: '2026-07-29T00:00:00Z', rawUserMessage: 'hi' }],
                workflowRuns: [],
                artifactRevisions: [
                  {
                    artifactId: 'art_x',
                    artifactType: 'requirement-set',
                    artifactVersion: 1,
                    lifecycleStatus: 'ready',
                    createdAt: '2026-07-29T00:00:00Z',
                    sourceTurnId: 'turn_x',
                  },
                ],
                veraResponses: [],
              }),
          };
        }
        return { ok: true, status: 200, text: async () => JSON.stringify(fixture) };
      }),
    );
    renderApp(`/projects/${projectId}`);
    expect(await screen.findByRole('tab', { name: 'Vera' })).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: /Show project history|History/i }));
    expect(await screen.findByText(/Artifact revisions/i)).toBeInTheDocument();
  });

  it('shows unsupported initialization error', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        text: async () =>
          JSON.stringify({
            error: {
              code: 'UNSUPPORTED_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE',
              message: 'Unsupported for fixture phase',
              supportedFamilies: [
                { family: 'wearable-tremor-monitor', examplePrompt: 'wrist-worn tremor example' },
              ],
            },
          }),
      }),
    );
    renderApp();
    await user.type(screen.getByLabelText(/Project idea/i), 'I want a cooking robot');
    await user.click(screen.getByRole('button', { name: /Create project/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Unsupported for fixture phase/i);
  });

  it('disables send while a turn is in flight', async () => {
    const user = userEvent.setup();
    const projectId = (fixture as { project: { projectId: string } }).project.projectId;
    let resolveTurn: ((value: unknown) => void) | undefined;
    const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      if (String(url).includes('/turns') && init?.method === 'POST') {
        return await new Promise((resolve) => {
          resolveTurn = resolve;
        });
      }
      if (String(url).includes('/history')) {
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify(historyPayload(projectId)),
        };
      }
      return { ok: true, status: 200, text: async () => JSON.stringify(fixture) };
    });
    vi.stubGlobal('fetch', fetchMock);
    renderApp(`/projects/${projectId}`);
    await screen.findByRole('tab', { name: 'Vera' });
    await user.click(screen.getByRole('tab', { name: 'Vera' }));
    expect(await screen.findByRole('heading', { name: 'Vera' })).toBeInTheDocument();
    const turnInput = screen.getByLabelText(/Continue the conversation/i);
    await user.clear(turnInput);
    await user.type(turnInput, 'Need six months battery');
    expect(turnInput).toHaveValue('Need six months battery');
    const send = screen.getByRole('button', { name: /Send to Vera/i });
    expect(send).toBeEnabled();
    await user.click(send);
    expect(await screen.findByRole('button', { name: /Updating/i })).toBeDisabled();
    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes('/turns'))).toBe(true);
    resolveTurn?.({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          schemaVersion: '1.0.0',
          currentState: fixture,
          changeIntent: {
            schemaVersion: '1.0.0',
            operation: 'add-requirement',
            targetArtifactType: 'requirement-set',
            requestedChange: 'Need six months battery',
            sourceTurnId: 'turn_abcdefghijklmnop',
            confidence: 'high',
            ambiguities: [],
            requiresUserConfirmation: false,
          },
          impactAnalysis: {
            schemaVersion: '1.0.0',
            changed: ['requirement-set'],
            affected: ['next-action'],
            stale: [],
            regenerate: ['requirement-set', 'next-action'],
            unchanged: ['project-brief'],
            reasonByArtifact: [],
          },
          changedArtifactTypes: ['requirement-set'],
          regeneratedArtifactTypes: ['requirement-set', 'next-action'],
        }),
    });
  });

  it('renders figma shell and selects live plus placeholder artifacts', async () => {
    const user = userEvent.setup();
    const projectId = (fixture as { project: { projectId: string } }).project.projectId;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (url: string) => {
        if (String(url).includes('/history')) {
          return { ok: true, status: 200, text: async () => JSON.stringify(historyPayload(projectId)) };
        }
        return { ok: true, status: 200, text: async () => JSON.stringify(fixture) };
      }),
    );
    renderApp(`/projects/${projectId}`);
    await screen.findByTestId('figma-shell');

    await user.click(screen.getByRole('button', { name: /^Requirements$/i }));
    expect(await screen.findByTestId('workspace-requirements')).toBeInTheDocument();
    expect(screen.getByText(/Total:/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^Architecture$/i }));
    expect(await screen.findByTestId('workspace-architecture')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^Components$/i }));
    expect(await screen.findByTestId('workspace-component-plan')).toBeInTheDocument();
    expect(screen.getByTestId('component-plan-summary')).toBeInTheDocument();
    expect(screen.getByTestId('component-plan-role-list')).toHaveTextContent(/role/i);

    await user.click(screen.getByRole('button', { name: /^Firmware$/i }));
    expect(screen.getByTestId('artifact-placeholder')).toHaveTextContent(/Firmware scaffold unavailable/i);

    expect(screen.queryByText(/BMI270/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/T-008/i)).not.toBeInTheDocument();
  });

  it('opens command palette and navigates to overview', async () => {
    const user = userEvent.setup();
    const projectId = (fixture as { project: { projectId: string } }).project.projectId;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (url: string) => {
        if (String(url).includes('/history')) {
          return { ok: true, status: 200, text: async () => JSON.stringify(historyPayload(projectId)) };
        }
        return { ok: true, status: 200, text: async () => JSON.stringify(fixture) };
      }),
    );
    renderApp(`/projects/${projectId}`);
    await screen.findByTestId('figma-shell');
    await user.click(screen.getByRole('button', { name: /Open command palette/i }));
    const dialog = screen.getByRole('dialog', { name: /Command palette/i });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    await user.click(within(dialog).getByRole('button', { name: /Open Overview/i }));
    expect(await screen.findByTestId('project-overview')).toBeInTheDocument();
  });

  it('keeps registry order stable for shuffled lookups', () => {
    const shuffled = [...ARTIFACT_ORDER].reverse();
    for (const key of shuffled) {
      expect(ARTIFACT_REGISTRY[key].routeKey).toBe(key);
    }
    expect(ARTIFACT_ORDER).toHaveLength(8);
  });
});
