/**
 * A sidecar that is real about the parts these suites measure.
 *
 * It binds a loopback socket the operating system chooses, announces it with
 * the same one-line handshake the Nexus API uses, and reports back whatever
 * `Authorization` header it was sent alongside the token it was started with,
 * plus the storage configuration the shell spawned it with. That is enough to
 * prove the shell resolved a live address, handed the renderer the same
 * credential the service received, and told the service where the student's
 * projects live - without needing a Python runtime or the real API on the
 * machine running the suite.
 */
import { createServer } from 'node:http';

const expectedToken = process.env.NEXUS_API_SESSION_TOKEN ?? '';

const server = createServer((request, response) => {
  // The renderer is a `file://` document, so its origin is `null` and any
  // request carrying an Authorization header is preflighted.
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization',
    'Content-Type': 'application/json',
  };

  if (request.method === 'OPTIONS') {
    response.writeHead(204, headers);
    response.end();
    return;
  }

  response.writeHead(200, headers);
  response.end(
    JSON.stringify({
      authorization: request.headers.authorization ?? null,
      expectedToken,
      storageBackend: process.env.NEXUS_STORAGE_BACKEND ?? null,
      databaseUrl: process.env.NEXUS_DATABASE_URL ?? null,
      pid: process.pid,
    }),
  );
});

server.listen(Number(process.env.NEXUS_API_PORT ?? '0'), '127.0.0.1', () => {
  const address = server.address();
  process.stdout.write(
    `${JSON.stringify({
      event: 'nexus.api.listening',
      schemaVersion: '1.0.0',
      host: '127.0.0.1',
      port: address.port,
      pid: process.pid,
    })}\n`,
  );
});
