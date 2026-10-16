import type { ExecutionRun } from '@nexus/contracts';

type RuntimeIdentity = NonNullable<ExecutionRun['runtimeIdentity']> & {
  securityLevel?: 'limited' | 'isolated';
  networkPolicy?: 'none' | 'restricted';
};

export function RuntimeIdentitySummary({
  identity,
  errorCode,
}: {
  identity?: RuntimeIdentity | null;
  errorCode?: string | null;
}) {
  if (errorCode === 'RUNTIME_UNAVAILABLE') {
    return (
      <span data-testid="runtime-identity" data-unavailable="true">
        Runtime unavailable
      </span>
    );
  }
  if (!identity) {
    return null;
  }
  const level = identity.securityLevel;
  const isolation =
    level === 'isolated'
      ? 'isolated container'
      : level === 'limited'
        ? 'limited process'
        : identity.runtimeKind;
  return (
    <span
      data-testid="runtime-identity"
      data-runtime-kind={identity.runtimeKind}
      data-security-level={level ?? ''}
    >
      {identity.runtimeKind} · {isolation}
    </span>
  );
}
