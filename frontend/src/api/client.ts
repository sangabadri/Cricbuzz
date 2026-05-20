import type {
  LiveScorecard,
  MatchSummary,
  PartnershipTracker,
} from "../types/api";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

export function fetchLiveScorecard(
  matchId: number,
  inningsNumber?: number,
): Promise<LiveScorecard> {
  const params = new URLSearchParams();
  if (inningsNumber != null) {
    params.set("innings_number", String(inningsNumber));
  }
  const qs = params.toString();
  return request<LiveScorecard>(
    `/api/v1/matches/${matchId}/scorecard${qs ? `?${qs}` : ""}`,
  );
}

export function fetchMatchSummary(matchId: number): Promise<MatchSummary> {
  return request<MatchSummary>(`/api/v1/matches/${matchId}/summary`);
}

export function fetchPartnerships(inningsId: number): Promise<PartnershipTracker> {
  return request<PartnershipTracker>(
    `/api/v1/innings/${inningsId}/partnerships`,
  );
}
