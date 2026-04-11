// In production (served by FastAPI), use relative path.
// In dev (Vite proxy), also use relative path — Vite proxies /api to FastAPI.
const BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface Player {
  id: number;
  web_name: string;
  team: string;
  team_short: string;
  position: string;
  now_cost: number;
  form: number;
  points_per_game: number;
  total_points: number;
  minutes: number;
  goals_scored: number;
  assists: number;
  clean_sheets: number;
  xG: number;
  xA: number;
  xG_per90: number;
  xA_per90: number;
  pts_per90: number;
  selected_by_percent: number;
  transfers_in_event: number;
  transfers_out_event: number;
  net_transfers: number;
  status: string;
  news: string;
  chance_of_playing: number | null;
  cost_change_event: number;
  ownership: number;
  pressure: number;
  // defensive
  tackles: number;
  recoveries: number;
  cbi: number;
  defcon: number;
  set_piece_notes?: string;
}

export interface TeamPlayer extends Player {
  is_captain: boolean;
  is_vice_captain: boolean;
  multiplier: number;
  is_bench: boolean;
  bench_order: number;
  xPts_1: number;
  xPts_3: number;
  xPts_5: number;
  avg_fdr: number;
}

export interface TeamSummary {
  team_id: number;
  players: TeamPlayer[];
  projected_1: number;
  projected_3: number;
  projected_5: number;
  squad_strength: number;
  weak_spots: string[];
}

export interface CaptainPick {
  rank: number;
  id: number;
  player: string;
  team: string;
  position: string;
  cost: string;
  fixture: string;
  is_home: boolean;
  captain_score: number;
  form_score: number;
  fixture_ease: number;
  xg_per90: number;
  xa_per90: number;
  haul_rate: number;
  xpts_next_gw: number;
  score: number;
  reason: string;
}

export interface FixturePrediction {
  gameweek: number;
  fixture_id: number;
  kickoff_time: string;
  home_team: string;
  away_team: string;
  home_predicted_goals: number;
  away_predicted_goals: number;
  home_cs_pct: number;
  away_cs_pct: number;
  predicted_home_goals: number;
  predicted_away_goals: number;
  source: string;
}

export interface NewsItem {
  title: string;
  link: string;
  published: string;
  headline: string;
  summary: string;
  timestamp: string;
}

export interface FDREntry {
  team: string;
  gameweeks: { gw: number; opponent: string; fdr: number; is_home: boolean }[];
}

export interface BettingOdds {
  home_team: string;
  away_team: string;
  home_win: number;
  draw: number;
  away_win: number;
  over_2_5: number;
  under_2_5: number;
}

export interface TransferSuggestion {
  rank: number;
  out_player: string;
  in_player: string;
  out_team: string;
  in_team: string;
  out_position: string;
  delta_value: number;
  out_cost: number;
  in_cost: number;
  out_form: number;
  in_form: number;
  out_fdr: number;
  in_fdr: number;
  delta_points: number;
  cost_impact: number;
  form_change: number;
}

export interface PlayerProjection {
  gw: number;
  projected_points: number;
  cumulative: number;
  opponent: string;
  fdr: number;
}

export interface PlayerGWHistory {
  gw: number;
  points: number;
}

export interface PlayerDetail extends Player {
  name: string;
  season_stats: Record<string, unknown>;
  defensive_stats: Record<string, unknown> | null;
  recent_history: Record<string, unknown>[];
  projections: Record<string, unknown> | null;
  upcoming_fixtures: Record<string, unknown>[];
  set_piece_notes: string[];
  history: PlayerGWHistory[];
  upcoming: { gw: number; opponent: string; fdr: number; is_home: boolean }[];
}

export interface DataSource {
  source: string;
  status: string;
  records_upserted: number;
  started_at: string;
  finished_at: string;
  duration_secs: number;
  age_secs: number;
  error_message: string | null;
  records: number;
  last_updated: string;
  duration: string;
}

export interface FormPlayer {
  rank: number;
  id: number;
  player: string;
  team: string;
  position: string;
  cost: number;
  form: number;
  xg_per90: number;
  xa_per90: number;
  pts_per90: number;
}

export interface PricePlayer {
  rank: number;
  player: string;
  team: string;
  position: string;
  price: number;
  ownership_pct: number;
  transfers_in_event: number;
  transfers_out_event: number;
  net_transfers_event: number;
  pressure: number;
}

export interface LeagueSummary {
  league_id: number;
  name: string;
  entry_count: number;
  fetched_at: string;
}

export interface LeagueStanding {
  entry_id: number;
  player_name: string;
  entry_name: string;
  rank: number;
  total: number;
  event_total: number;
}

export interface LeagueStandings {
  league_id: number;
  name: string;
  fetched_at: string;
  standings: LeagueStanding[];
}

export interface OpponentTransfer {
  event: number;
  element_in: number;
  element_in_name: string;
  element_in_cost: number;
  element_out: number;
  element_out_name: string;
  element_out_cost: number;
  time: string;
}

export interface OpponentTeam {
  entry_id: number;
  manager_name: string;
  team_name: string;
  gameweek: number;
  gameweek_points: number;
  overall_points: number;
  overall_rank: number;
  bank: number;
  squad_value: number;
  free_transfers: number;
  transfers_made: number;
  players: {
    id: number;
    web_name: string;
    team: string;
    position: string;
    cost: number;
    form: number;
    xpts_next_gw: number;
    event_points: number;
    gw_points: number;
    gw_bonus: number;
    status: string;
    news: string;
    is_starter: boolean;
    squad_position: number;
    is_captain: boolean;
    is_vice_captain: boolean;
    multiplier: number;
  }[];
  transfers: OpponentTransfer[];
}

export interface MatchEvent {
  minute: number;
  extra_minute: number | null;
  type: string;
  detail: string;
  player: string;
  assist: string | null;
  team: string;
}

export interface MatchScore {
  fixture_id: number;
  status: string;
  status_long: string;
  elapsed: number | null;
  home_team: string;
  away_team: string;
  home_goals: number | null;
  away_goals: number | null;
  kickoff: string;
  events: MatchEvent[];
}

export interface LeagueScores {
  id: number;
  name: string;
  country: string;
  matches: MatchScore[];
}

export interface ScoresResponse {
  date: string;
  leagues: LeagueScores[];
}

export const api = {
  // Team
  getTeam: () => get<TeamSummary>('/me/team'),
  getTeamAnalysis: (weeks = 5) => get<TeamSummary>(`/me/analyse?weeks=${weeks}`),
  loadTeam: (teamId: number) => post<{ message: string }>(`/me/login?team_id=${teamId}`),

  // Captain
  getCaptains: (top = 5) => get<CaptainPick[]>(`/captain/pick?top=${top}`),

  // Predictions
  getPredictions: (gw?: number) => {
    const q = gw ? `?gameweek=${gw}` : '';
    return get<FixturePrediction[]>(`/predict/goals${q}`);
  },
  getCleansheets: (gw?: number, top = 20) => {
    const params = new URLSearchParams();
    if (gw) params.set('gameweek', String(gw));
    params.set('top', String(top));
    return get<unknown[]>(`/predict/cleansheets?${params}`);
  },

  // News
  getNews: (top = 10) => get<NewsItem[]>(`/data/news?top=${top}`),

  // Players
  getPlayers: (params?: Record<string, string>) => {
    const q = params ? '?' + new URLSearchParams(params).toString() : '';
    return get<FormPlayer[]>(`/players/form${q}`);
  },
  getDifferentials: (params?: Record<string, string>) => {
    const q = params ? '?' + new URLSearchParams(params).toString() : '';
    return get<unknown[]>(`/players/differentials${q}`);
  },
  getPlayer: (id: number) => get<PlayerDetail>(`/players/${id}`),
  searchPlayers: (q: string) => get<unknown[]>(`/players/search?q=${q}`),
  getSetpieces: (team?: string) => {
    const q = team ? `?team=${encodeURIComponent(team)}` : '';
    return get<unknown[]>(`/players/setpieces${q}`);
  },

  // Fixtures
  getFixtures: (gw?: number) => {
    const q = gw ? `?gameweek=${gw}` : '';
    return get<unknown[]>(`/fixtures${q}`);
  },
  getFDR: (weeks = 6) => get<unknown>(`/fixtures/difficulty?weeks=${weeks}`),
  getBettingOdds: (gw?: number) => {
    const q = gw ? `?gameweek=${gw}` : '';
    return get<BettingOdds[]>(`/fixtures/odds${q}`);
  },

  // Transfers
  getTransferSuggestions: (params?: Record<string, string>) => {
    const q = params ? '?' + new URLSearchParams(params).toString() : '';
    return get<TransferSuggestion[]>(`/transfers/suggest${q}`);
  },
  comparePlayers: (p1: string, p2: string) =>
    get<unknown>(`/transfers/compare?player1=${encodeURIComponent(p1)}&player2=${encodeURIComponent(p2)}`),

  // Prices
  getPriceRisers: (top = 20) => get<PricePlayer[]>(`/prices/risers?top=${top}`),
  getPriceFallers: (top = 20) => get<PricePlayer[]>(`/prices/fallers?top=${top}`),

  // Leagues
  getLeagues: () => get<LeagueSummary[]>('/leagues'),
  addLeague: (leagueId: number) => post<{ status: string; league_id: number; name: string; entries: number }>(`/leagues?league_id=${leagueId}`),
  removeLeague: (leagueId: number) =>
    fetch(`${BASE}/leagues/${leagueId}`, { method: 'DELETE' }).then(r => r.json()),
  getLeagueStandings: (leagueId: number, force = false) =>
    get<LeagueStandings>(`/leagues/${leagueId}/standings?force=${force}`),
  getLeagueEntry: (leagueId: number, entryId: number) =>
    get<OpponentTeam>(`/leagues/${leagueId}/entry/${entryId}`),

  // Scores
  getTodayScores: (date?: string) => {
    const q = date ? `?date=${date}` : '';
    return get<ScoresResponse>(`/scores/today${q}`);
  },

  // Data management
  getDataStatus: () => get<DataSource[]>('/data/status'),
  refreshAll: (source = 'all', force = false) =>
    post<Record<string, string>>(`/data/refresh?source=${source}&force=${force}`),
};
