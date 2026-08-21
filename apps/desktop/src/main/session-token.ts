import { randomBytes } from 'node:crypto';

/**
 * Bytes of entropy behind a session token.
 *
 * The token is the only thing standing between the local API and any other
 * process on the machine that can reach loopback, so it is sized to be
 * unguessable rather than convenient to read.
 */
const TOKEN_BYTES = 32;

/**
 * Mint the shared secret for one run of the shell.
 *
 * The token lives in the main process's memory and is handed to the sidecar
 * through its environment and to the renderer through the preload bridge. It is
 * deliberately never written to disk: a token in a config file outlives the
 * session it was minted for and becomes a credential anyone who can read the
 * user's home directory can replay.
 */
export function createSessionToken(): string {
  return randomBytes(TOKEN_BYTES).toString('hex');
}
