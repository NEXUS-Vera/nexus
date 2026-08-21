import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import { ServiceRestartNotice } from './ServiceRestartNotice';

/**
 * The desktop shell reloads this page when its local API sidecar is replaced,
 * because the new address reaches the renderer as a value on the preload bridge
 * rather than as a channel it can be pushed down. A reload nobody asked for
 * reads as the application losing the student's place unless something says
 * otherwise, which is the whole job of this component.
 */

function installShellBridge(shell: unknown): void {
  (globalThis as { nexus?: unknown }).nexus = { api: {}, shell };
}

afterEach(() => {
  delete (globalThis as { nexus?: unknown }).nexus;
});

describe('ServiceRestartNotice', () => {
  it('says nothing in a browser, where there is no shell and nothing restarted', () => {
    const { container } = render(<ServiceRestartNotice />);

    expect(container).toBeEmptyDOMElement();
  });

  it('says nothing on an ordinary launch', () => {
    installShellBridge({ serviceRestarted: false });

    const { container } = render(<ServiceRestartNotice />);

    expect(container).toBeEmptyDOMElement();
  });

  it('reports the restart, and that unsent work was not kept', async () => {
    installShellBridge({ serviceRestarted: true });

    render(<ServiceRestartNotice />);

    const notice = screen.getByRole('status');
    expect(notice).toHaveTextContent(/restarted its local service/i);
    // The student needs to know why what they had typed is gone, not only that
    // something happened.
    expect(notice).toHaveTextContent(/not kept/i);

    await userEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    expect(screen.queryByRole('status')).toBeNull();
  });
});
