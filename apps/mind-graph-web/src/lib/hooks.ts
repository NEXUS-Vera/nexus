/** TanStack Query bindings. Cache policy from Frontend/06 §4.2. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./api";

export const useStats = () => useQuery({ queryKey: ["stats"], queryFn: api.stats, staleTime: 5 * 60_000 });
export const useFrontier = (k = 3) =>
  useQuery({ queryKey: ["frontier", k], queryFn: () => api.frontier(k), staleTime: 30_000, refetchOnWindowFocus: true });
export const useTensions = () => useQuery({ queryKey: ["tensions"], queryFn: api.tensions, staleTime: 60_000 });
export const useExplain = (id: string | null) =>
  useQuery({ queryKey: ["explain", id], queryFn: () => api.explain(id as string), enabled: !!id });
export const useQueryGraph = (q: string, lens?: string) =>
  useQuery({ queryKey: ["query", q, lens], queryFn: () => api.query(q, lens), enabled: q.trim().length > 1 });
export const useCalibration = () => useQuery({ queryKey: ["calibration"], queryFn: api.calibration, staleTime: 60_000 });
/** ⭐ The main verb, and the only mutation that is really a read.
 *
 * A mutation rather than a query because a turn COSTS MONEY and calls models:
 * `useQuery` would refetch it on window focus, on remount, on cache expiry.
 * An answer that silently re-bills itself because the student alt-tabbed is
 * the kind of bug you only find on the invoice.
 */
export function useTurn() {
  return useMutation({ mutationFn: (q: string) => api.turn(q) });
}

/** ⚠️ Long staleTime on purpose: the log only changes when something is
 *  validated or retracted, and refetching a document while it is being read
 *  is how a reader loses their place. */
export const useCompanion = (opts: { id?: string; q?: string } = {}) =>
  useQuery({ queryKey: ["companion", opts.id ?? null, opts.q ?? null],
             queryFn: () => api.companion(opts), staleTime: 2 * 60_000 });
export const useLog = () => useQuery({ queryKey: ["log"], queryFn: api.log, staleTime: 5 * 60_000 });
export const useReview = () => useQuery({ queryKey: ["review"], queryFn: api.review, staleTime: 30_000 });

/** ⭐ Optimistic, per Frontend/06 §4.3 — but the ledger is the truth, so any
 *  failure rolls back rather than being papered over. */
export function useDecide() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ids, accept }: { ids: string[]; accept: boolean }) => api.decide(ids, accept),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function usePredict() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.predict,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["stats"] }),
  });
}
