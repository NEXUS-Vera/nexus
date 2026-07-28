import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import fixture from '../../../packages/contracts/examples/valid/project-initialization-result/project-initialization-result.json';
import type { ProjectInitializationResult } from '@nexus/contracts';
import { selectArtifactByType } from './artifacts';

function shuffledFixture(): ProjectInitializationResult {
  const copy = structuredClone(fixture) as unknown as ProjectInitializationResult;
  const byType = Object.fromEntries(
    [...copy.artifacts].map((artifact) => [artifact.artifactType, artifact]),
  );
  copy.artifacts = [
    byType['next-action'],
    byType['functional-architecture'],
    byType['requirement-set'],
    byType['project-brief'],
  ] as ProjectInitializationResult['artifacts'];
  return copy;
}

describe('Vera initialization prototype', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders empty state and can populate an example prompt', async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(
      screen.getByText(/Tell Vera what embedded product you want to build/i),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Wearable tremor monitor/i }));
    expect((screen.getByLabelText(/Product idea/i) as HTMLTextAreaElement).value).toContain(
      'wrist-worn device',
    );
  });

  it('renders Vera response and four artifact cards from artifactType', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify(fixture),
      }),
    );
    render(<App />);
    await user.click(screen.getByRole('button', { name: /Wearable tremor monitor/i }));
    await user.click(screen.getByRole('button', { name: /Initialize project/i }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Vera' })).toBeInTheDocument();
    });
    expect(screen.getByRole('heading', { name: 'Project Brief' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Requirements' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Functional Architecture' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Next Action' })).toBeInTheDocument();
    expect(screen.getByText(/Completion:/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Lifecycle/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Evidence/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Approval/i).length).toBeGreaterThan(0);
  });

  it('renders all four cards when artifacts arrive shuffled', async () => {
    const user = userEvent.setup();
    const payload = shuffledFixture();
    expect(payload.artifacts[0]?.artifactType).toBe('next-action');
    expect(selectArtifactByType(payload.artifacts, 'project-brief')?.artifactType).toBe(
      'project-brief',
    );
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify(payload),
      }),
    );
    render(<App />);
    await user.click(screen.getByRole('button', { name: /Wearable tremor monitor/i }));
    await user.click(screen.getByRole('button', { name: /Initialize project/i }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Project Brief' })).toBeInTheDocument();
    });
    expect(screen.getByRole('heading', { name: 'Requirements' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Functional Architecture' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Next Action' })).toBeInTheDocument();
  });

  it('shows unsupported error', async () => {
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
                {
                  family: 'wearable-tremor-monitor',
                  examplePrompt: 'wrist-worn tremor example',
                },
              ],
            },
          }),
      }),
    );
    render(<App />);
    await user.type(screen.getByLabelText(/Product idea/i), 'I want a cooking robot');
    await user.click(screen.getByRole('button', { name: /Initialize project/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Unsupported for fixture phase/i);
  });

  it('shows ambiguous error', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        text: async () =>
          JSON.stringify({
            error: {
              code: 'AMBIGUOUS_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE',
              message: 'Matches multiple families',
            },
          }),
      }),
    );
    render(<App />);
    await user.type(screen.getByLabelText(/Product idea/i), 'greenhouse tremor rover');
    await user.click(screen.getByRole('button', { name: /Initialize project/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Narrow the prompt/i);
  });

  it('shows network failure and allows retry', async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: async () => JSON.stringify(fixture),
      });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    await user.type(screen.getByLabelText(/Product idea/i), 'wrist-worn tremor monitor');
    await user.click(screen.getByRole('button', { name: /Initialize project/i }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/Network failure/i);
    expect(alert).toHaveAttribute('id', 'form-error');
    expect(document.querySelector('form.prompt-form')).toHaveAttribute(
      'aria-describedby',
      'form-error',
    );
    await user.click(screen.getByRole('button', { name: /Retry/i }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Vera' })).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('shows explicit HTTP 500 server failure and keeps the prompt for retry', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        text: async () =>
          JSON.stringify({
            error: {
              code: 'INITIALIZATION_PACKAGE_VALIDATION_FAILED',
              message: 'Project initialization failed validation.',
            },
          }),
      }),
    );
    render(<App />);
    await user.type(screen.getByLabelText(/Product idea/i), 'wrist-worn tremor monitor');
    await user.click(screen.getByRole('button', { name: /Initialize project/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/No valid package was created/i);
    expect((screen.getByLabelText(/Product idea/i) as HTMLTextAreaElement).value).toContain(
      'wrist-worn',
    );
    expect(screen.getByRole('button', { name: /Initialize project/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
  });

  it('supports keyboard form submission', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(fixture),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    const textarea = screen.getByLabelText(/Product idea/i);
    await user.click(textarea);
    await user.paste('wrist-worn tremor monitor for later analysis');
    await user.keyboard('{Enter}');
    // Enter alone in textarea does not submit; Ctrl/Meta+Enter is not required by the app.
    // Submit via the form's primary action activated from keyboard focus.
    screen.getByRole('button', { name: /Initialize project/i }).focus();
    await user.keyboard('{Enter}');
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
  });

  it('announces loading state via aria-live region', async () => {
    const user = userEvent.setup();
    let resolveFetch: ((value: unknown) => void) | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveFetch = resolve;
          }),
      ),
    );
    render(<App />);
    await user.click(screen.getByRole('button', { name: /Wearable tremor monitor/i }));
    await user.click(screen.getByRole('button', { name: /Initialize project/i }));
    const live = document.querySelector('[aria-live="polite"]');
    expect(live).not.toBeNull();
    expect(live).toHaveTextContent(/Understanding your project|Preparing|Validating/i);
    resolveFetch?.({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(fixture),
    });
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Vera' })).toBeInTheDocument();
    });
  });

  it('prevents duplicate submission while loading', async () => {
    const user = userEvent.setup();
    let resolveFetch: ((value: unknown) => void) | undefined;
    const fetchMock = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    await user.click(screen.getByRole('button', { name: /Wearable tremor monitor/i }));
    await user.click(screen.getByRole('button', { name: /Initialize project/i }));
    expect(screen.getByRole('button', { name: /Initializing/i })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolveFetch?.({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(fixture),
    });
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Vera' })).toBeInTheDocument();
    });
  });
});
