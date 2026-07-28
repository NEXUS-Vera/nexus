import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import fixture from '../../../packages/contracts/examples/valid/project-initialization-result/project-initialization-result.json';

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

  it('shows network failure', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    render(<App />);
    await user.type(screen.getByLabelText(/Product idea/i), 'wrist-worn tremor monitor');
    await user.click(screen.getByRole('button', { name: /Initialize project/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Network failure/i);
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
