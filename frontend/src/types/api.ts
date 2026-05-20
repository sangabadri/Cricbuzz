export interface LiveScorecard {
  match_id: number;
  innings_id: number;
  innings_number: number;
  batting_team_id: number;
  batting_team_name: string;
  status: string;
  total_runs: number;
  total_wickets: number;
  overs_display: string;
  legal_balls_bowled: number;
  extras_total: number;
  current_run_rate: number | null;
  required_run_rate: number | null;
  runs_required: number | null;
  balls_remaining: number | null;
  target_runs: number | null;
  last_five_overs_runs: number;
  last_five_overs_run_rate: number | null;
}

export interface Partnership {
  partnership_number: number;
  batsman_1_id: number;
  batsman_1_name: string;
  batsman_2_id: number;
  batsman_2_name: string;
  runs: number;
  balls_faced: number;
  is_current: boolean;
}

export interface PartnershipTracker {
  innings_id: number;
  current_partnership: Partnership | null;
  past_partnerships: Partnership[];
}

export interface InningsSummaryBlock {
  innings_number: number;
  batting_team_name: string;
  total_runs: number;
  total_wickets: number;
  overs_display: string;
  status: string;
}

export interface FallOfWicket {
  wicket_number: number;
  runs_at_fall: number;
  overs_at_fall: string;
  dismissed_player_id: number;
  dismissed_player_name: string;
  dismissal: string;
  sequence_number: number;
}

export interface MatchSummary {
  match_id: number;
  venue: string;
  match_date: string;
  format: string;
  status: string;
  team_a_name: string;
  team_b_name: string;
  winner_name: string | null;
  result_summary: string | null;
  player_of_match_id: number | null;
  player_of_match_name: string | null;
  innings: InningsSummaryBlock[];
  fall_of_wickets: FallOfWicket[];
}
