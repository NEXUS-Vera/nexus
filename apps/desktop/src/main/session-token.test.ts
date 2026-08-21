import { describe, expect, it } from 'vitest';

import { createSessionToken } from './session-token.js';

describe('createSessionToken', () => {
  it('mints an unpredictable token that is unique per session', () => {
    const minted = new Set(Array.from({ length: 64 }, () => createSessionToken()));

    for (const token of minted) {
      // 256 bits of CSPRNG output, hex encoded. Anything shorter or derived
      // from something guessable (a pid, a clock, a machine id) would let a
      // process the user did not authorise talk to their local API.
      expect(token).toMatch(/^[0-9a-f]{64}$/);
    }
    expect(minted.size).toBe(64);
  });
});
