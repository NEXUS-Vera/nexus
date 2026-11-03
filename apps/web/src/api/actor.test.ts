import { describe, expect, it } from 'vitest';
import { USER_ACTOR } from './actor';

describe('USER_ACTOR', () => {
  it('matches the actor-reference contract for the local user', () => {
    expect(USER_ACTOR.actorId).toMatch(/^actor_[A-Za-z0-9]{16,}$/);
    expect(USER_ACTOR).toMatchObject({
      schemaVersion: '1.0.0',
      actorType: 'user',
      displayName: 'User',
    });
  });
});
