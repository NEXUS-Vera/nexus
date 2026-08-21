import { useState } from 'react';

/**
 * Tells the student that the local service was replaced and the view reloaded.
 *
 * The desktop shell reloads this page when its API sidecar crashes and comes
 * back on a different port, because the address reaches the renderer through
 * the preload bridge as a value rather than as a channel it can be pushed down.
 * The reload keeps the route, since the shell re-requests the same fragment,
 * but it cannot keep anything held only in this page's memory - a half-written
 * message to Vera among it. An unexplained reload reads as the application
 * losing the student's place, so the shell reports that it was a recovery and
 * this says so.
 */

function serviceRestarted(): boolean {
  // Read off `globalThis` rather than `window`, so this stays evaluable in the
  // Node-based test environment, and treated as absent unless it is exactly
  // `true`: in a browser there is no shell and nothing restarted.
  const shell = (globalThis as { nexus?: { shell?: { serviceRestarted?: unknown } } }).nexus?.shell;
  return shell?.serviceRestarted === true;
}

export function ServiceRestartNotice() {
  // Read once, at mount: the flag describes this load, and the student
  // dismissing it must not be undone by anything that re-renders afterwards.
  const [visible, setVisible] = useState(serviceRestarted);

  if (!visible) {
    return null;
  }

  return (
    <div className="service-restart-notice" role="status">
      <p>
        Nexus restarted its local service and reloaded this view. Anything you had typed but not
        yet sent was not kept.
      </p>
      <button
        type="button"
        onClick={() => {
          setVisible(false);
        }}
        aria-label="Dismiss"
      >
        Dismiss
      </button>
    </div>
  );
}
