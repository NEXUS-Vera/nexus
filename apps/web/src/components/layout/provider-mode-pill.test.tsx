import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { getHealthz } from '../../api/client';
import { ProviderModePill } from './provider-mode-pill';
vi.mock('../../api/client', () => ({ getHealthz: vi.fn() }));
it.each([['llm', 'LIVE'], ['fixture', 'FIXTURE']])('shows %s and safe diagnostics', async (provider, label) => {
  vi.mocked(getHealthz).mockResolvedValue({ status: 'ok', initializationProvider: provider, storageBackend: 'sqlite', apiKey: 'hidden-key' } as never);
  render(<ProviderModePill />);
  fireEvent.click(await screen.findByRole('button', { name: label }));
  expect(screen.getByRole('region')).toHaveTextContent('PlatformIO');
  expect(document.body.textContent).not.toContain('hidden-key');
  fireEvent.keyDown(screen.getByRole('region'), { key: 'Escape' });
  expect(screen.queryByRole('region')).not.toBeInTheDocument();
});
it('reports unavailable health without exposing errors', async () => {
  vi.mocked(getHealthz).mockRejectedValue(new Error('secret'));
  render(<ProviderModePill />);
  fireEvent.click(screen.getByRole('button', { name: 'UNKNOWN' }));
  expect(await screen.findByText('Provider health unavailable.')).toBeInTheDocument();
  expect(document.body.textContent).not.toContain('secret');
});
