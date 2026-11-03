import type { ArtifactCommand } from '@nexus/contracts';

export const USER_ACTOR = {
  schemaVersion: '1.0.0',
  actorId: 'actor_localoperator0000001',
  actorType: 'user',
  displayName: 'User',
} as const satisfies ArtifactCommand['requestedBy'];
