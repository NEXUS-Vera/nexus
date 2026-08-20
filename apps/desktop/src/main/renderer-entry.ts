import { accessSync, constants } from 'node:fs';
import path from 'node:path';

/**
 * Locating the built renderer, and saying so plainly when it is not there.
 *
 * Handing a missing path to `loadFile` produces `ERR_FAILED (-2)` beside a file
 * URL, which names neither the cause nor the remedy. The same path is reached
 * by a source checkout that was never built, by a build that is mid-flight, and
 * by an installation that was extracted incompletely - all of which a person
 * can fix once they are told which one it is.
 */

/** The renderer bundle is absent or unreadable. */
export class RendererBundleError extends Error {
  constructor(entryPath: string) {
    super(
      'The Nexus application interface is missing from this installation.\n\n' +
        `It was expected at ${entryPath}.\n\n` +
        'If you are running Nexus from a source checkout, build it first with ' +
        '`pnpm --filter @nexus/desktop build`. Otherwise the installation is ' +
        'incomplete or damaged, and reinstalling Nexus will replace it.',
    );
    this.name = 'RendererBundleError';
  }
}

/**
 * Resolve the renderer's entry document beneath an application root.
 *
 * Readability is checked rather than mere existence: an install that unpacked
 * with the wrong permissions has the file and still cannot load it.
 */
export function resolveRendererEntry(appPath: string): string {
  const entryPath = path.join(appPath, 'dist', 'renderer', 'index.html');

  try {
    accessSync(entryPath, constants.R_OK);
  } catch {
    throw new RendererBundleError(entryPath);
  }

  return entryPath;
}
