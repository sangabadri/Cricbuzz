import { useCallback, useMemo } from "react";
import {
  fetchLiveScorecard,
  fetchMatchSummary,
  fetchPartnerships,
} from "../api/client";
import type {
  LiveScorecard,
  MatchSummary,
  PartnershipTracker,
} from "../types/api";
import { usePolling } from "./usePolling";

export interface DashboardData {
  scorecard: LiveScorecard;
  summary: MatchSummary;
  partnerships: PartnershipTracker;
}

export function useLiveDashboard(matchId: number, inningsNumber?: number) {
  const fetchAll = useCallback(async (): Promise<DashboardData> => {
    const scorecard = await fetchLiveScorecard(matchId, inningsNumber);
    const [summary, partnerships] = await Promise.all([
      fetchMatchSummary(matchId),
      fetchPartnerships(scorecard.innings_id),
    ]);
    return { scorecard, summary, partnerships };
  }, [matchId, inningsNumber]);

  const polling = usePolling<DashboardData>({
    fetcher: fetchAll,
    intervalMs: 4000,
    enabled: matchId > 0,
  });

  const chasing = useMemo(() => {
    const sc = polling.data?.scorecard;
    return sc?.target_runs != null && sc.innings_number === 2;
  }, [polling.data?.scorecard]);

  return { ...polling, chasing };
}
