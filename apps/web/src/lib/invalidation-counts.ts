/** Count chain rows, not unique tests or historical assessment outcomes. */
export function countEvidenceInvalidations(
  chains: readonly { applicability?: { state?: string } | null }[],
): { staleCount: number; recheckCount: number } {
  let staleCount = 0;
  let recheckCount = 0;
  for (const chain of chains) {
    if (chain.applicability?.state === 'STALE') staleCount += 1;
    if (chain.applicability?.state === 'RECHECK_REQUIRED') recheckCount += 1;
  }
  return { staleCount, recheckCount };
}
