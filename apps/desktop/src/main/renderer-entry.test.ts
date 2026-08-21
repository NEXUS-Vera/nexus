import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, describe, expect, it } from 'vitest';

import { RendererBundleError, resolveRendererEntry } from './renderer-entry.js';

const scratchDirs: string[] = [];

afterEach(async () => {
  await Promise.all(scratchDirs.splice(0).map((dir) => rm(dir, { force: true, recursive: true })));
});

async function scratchAppDir(): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), 'nexus-renderer-'));
  scratchDirs.push(dir);
  return dir;
}

describe('resolveRendererEntry', () => {
  it('returns the entry document when the bundle is there', async () => {
    const appPath = await scratchAppDir();
    await mkdir(join(appPath, 'dist', 'renderer'), { recursive: true });
    const entry = join(appPath, 'dist', 'renderer', 'index.html');
    await writeFile(entry, '<!doctype html>', 'utf8');

    expect(resolveRendererEntry(appPath)).toBe(entry);
  });

  it('says the interface is missing rather than letting Chromium fail the load', async () => {
    const appPath = await scratchAppDir();

    // Chromium reports an absent document as `ERR_FAILED (-2)` next to a file
    // URL. That is not something a student can act on, and it is reached by a
    // damaged install just as readily as by an unbuilt checkout.
    let thrown: unknown;
    try {
      resolveRendererEntry(appPath);
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(RendererBundleError);
    expect((thrown as Error).message).toContain(join(appPath, 'dist', 'renderer', 'index.html'));
    expect((thrown as Error).message).toContain('pnpm --filter @nexus/desktop build');
  });
});
