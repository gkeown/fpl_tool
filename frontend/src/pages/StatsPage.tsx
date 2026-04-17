import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Search, X, ArrowLeft, Star, Trophy } from "lucide-react";

const LEAGUE_NAMES: Record<string, string> = {
  "eng.1": "Premier League",
  "eng.2": "Championship",
  "ita.1": "Serie A",
  "esp.1": "La Liga",
  "ger.1": "Bundesliga",
  "fra.1": "Ligue 1",
};

function PlayerSearchResults({ results, onSelect }: { results: any[]; onSelect: (p: any) => void }) {
  if (results.length === 0) {
    return <p className="text-center text-muted-foreground py-8">No players found</p>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {results.map((p: any) => (
        <Card
          key={p.id}
          className="cursor-pointer hover:bg-fpl-green/5 transition-colors"
          onClick={() => onSelect(p)}
        >
          <CardContent className="p-4 flex items-center gap-4">
            {p.photo && (
              <img
                src={p.photo}
                alt={p.name}
                className="w-12 h-12 rounded-full object-cover bg-muted"
              />
            )}
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm truncate">{p.name}</p>
              <p className="text-xs text-muted-foreground">{p.team} · {LEAGUE_NAMES[p.league] || p.league}</p>
              <div className="flex gap-1.5 mt-1">
                <Badge variant="outline" className="text-[10px]">{p.position || "N/A"}</Badge>
                <Badge variant="outline" className="text-[10px]">{p.nationality}</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function StatBox({ label, value, highlight }: { label: string; value: any; highlight?: boolean }) {
  return (
    <div className="p-2 rounded-md bg-muted/30">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</p>
      <p className={`text-sm font-semibold mt-0.5 tabular-nums ${highlight ? "text-fpl-green" : ""}`}>
        {value ?? "-"}
      </p>
    </div>
  );
}

function CompetitionStats({ stats }: { stats: any }) {
  const pos = (stats.position || "").toLowerCase();
  const isGK = pos.includes("goalkeeper");
  const isDef = pos.includes("defender");

  return (
    <Card className="card-stripe mb-4">
      <CardHeader className="pb-2 pt-4 px-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">
            {stats.league}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-[10px]">{stats.team}</Badge>
            {stats.rating && (
              <Badge className="bg-fpl-green/15 text-fpl-green border border-fpl-green/30 text-xs">
                <Star className="h-3 w-3 mr-0.5" />
                {stats.rating}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        {/* General stats */}
        <div className="grid grid-cols-4 sm:grid-cols-6 gap-2 mb-3">
          <StatBox label="Apps" value={stats.appearances} />
          <StatBox label="Starts" value={stats.lineups} />
          <StatBox label="Minutes" value={stats.minutes?.toLocaleString()} />
          <StatBox label="Goals" value={stats.goals} highlight={stats.goals > 0} />
          <StatBox label="Assists" value={stats.assists} highlight={stats.assists > 0} />
          <StatBox label="Rating" value={stats.rating} />
        </div>

        {/* Attacking / Shooting */}
        {!isGK && (
          <div className="mb-3">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">Attacking</p>
            <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
              <StatBox label="Shots" value={stats.shots_total} />
              <StatBox label="On Target" value={stats.shots_on} />
              <StatBox label="Key Passes" value={stats.passes_key} />
              <StatBox label="Dribbles" value={`${stats.dribbles_success}/${stats.dribbles_attempts}`} />
              <StatBox label="Pen Scored" value={stats.penalty_scored} />
              <StatBox label="Pen Missed" value={stats.penalty_missed} />
            </div>
          </div>
        )}

        {/* Passing */}
        <div className="mb-3">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">Passing</p>
          <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
            <StatBox label="Passes" value={stats.passes_total?.toLocaleString()} />
            <StatBox label="Accuracy" value={stats.passes_accuracy ? `${stats.passes_accuracy}%` : "-"} />
            <StatBox label="Key Passes" value={stats.passes_key} />
          </div>
        </div>

        {/* Defensive */}
        {(isDef || isGK || stats.tackles > 0) && (
          <div className="mb-3">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">Defensive</p>
            <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
              <StatBox label="Tackles" value={stats.tackles} />
              <StatBox label="Intercepts" value={stats.interceptions} />
              <StatBox label="Blocks" value={stats.blocks} />
              <StatBox label="Duels Won" value={`${stats.duels_won}/${stats.duels_total}`} />
            </div>
          </div>
        )}

        {/* GK specific */}
        {isGK && (
          <div className="mb-3">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">Goalkeeping</p>
            <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
              <StatBox label="Saves" value={stats.saves} />
              <StatBox label="Conceded" value={stats.goals_conceded} />
              <StatBox label="Pen Saved" value={stats.penalty_saved} />
            </div>
          </div>
        )}

        {/* Discipline */}
        <div>
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">Discipline</p>
          <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
            <StatBox label="Yellows" value={stats.yellow_cards} />
            <StatBox label="Reds" value={stats.red_cards} />
            <StatBox label="Fouls" value={stats.fouls_committed} />
            <StatBox label="Fouled" value={stats.fouls_drawn} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function XgSection({ xgData }: { xgData: any[] }) {
  if (!xgData || xgData.length === 0) return null;

  return (
    <Card className="card-stripe mb-4">
      <CardHeader className="pb-2 pt-4 px-4">
        <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">
          Expected Goals (Understat)
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/30">
                <th className="text-left px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Season</th>
                <th className="text-center px-2 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Apps</th>
                <th className="text-center px-2 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">G</th>
                <th className="text-center px-2 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">xG</th>
                <th className="text-center px-2 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">npxG</th>
                <th className="text-center px-2 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">A</th>
                <th className="text-center px-2 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">xA</th>
              </tr>
            </thead>
            <tbody>
              {xgData.map((s: any) => (
                <tr key={s.season} className="border-t border-border/20">
                  <td className="px-3 py-1.5 font-medium">{s.season}</td>
                  <td className="text-center px-2 py-1.5 tabular-nums">{s.games}</td>
                  <td className="text-center px-2 py-1.5 tabular-nums font-semibold">{s.goals}</td>
                  <td className="text-center px-2 py-1.5 tabular-nums text-fpl-green">{s.xG?.toFixed(2) ?? "-"}</td>
                  <td className="text-center px-2 py-1.5 tabular-nums">{s.npxG?.toFixed(2) ?? "-"}</td>
                  <td className="text-center px-2 py-1.5 tabular-nums font-semibold">{s.assists}</td>
                  <td className="text-center px-2 py-1.5 tabular-nums text-fpl-green">{s.xA?.toFixed(2) ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function PlayerDetail({ playerId, league, onBack }: { playerId: string; league: string; onBack: () => void }) {
  const detail = useQuery({
    queryKey: ["playerStats", playerId, league],
    queryFn: () => api.getPlayerStats(playerId, undefined, league),
  });

  const xg = useQuery({
    queryKey: ["playerXg", playerId, league],
    queryFn: () => api.getPlayerXg(playerId, league),
  });

  const data = detail.data as any;
  const player = data?.player;
  const statistics = data?.statistics ?? [];
  const xgData = (xg.data as any)?.xg_data ?? [];

  return (
    <div>
      <Button variant="ghost" size="sm" onClick={onBack} className="mb-4 -ml-2">
        <ArrowLeft className="h-4 w-4 mr-1" /> Back to Search
      </Button>

      {detail.isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-16 w-64" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : detail.isError ? (
        <Alert variant="destructive">
          <AlertDescription>Failed to load player data. The player may not have stats for this season.</AlertDescription>
        </Alert>
      ) : player ? (
        <>
          {/* Player header */}
          <div className="flex items-start gap-4 mb-4">
            {player.photo && (
              <img
                src={player.photo}
                alt={player.name}
                className="w-16 h-16 rounded-full object-cover bg-muted"
              />
            )}
            <div>
              <h2 className="text-2xl font-display font-bold">{player.name}</h2>
              <p className="text-sm text-muted-foreground">
                {player.team} · {player.position} · {player.nationality}
              </p>
              <div className="flex flex-wrap gap-2 mt-1">
                {player.age && <Badge variant="outline" className="text-xs">Age: {player.age}</Badge>}
                {player.height && <Badge variant="outline" className="text-xs">{player.height}</Badge>}
              </div>
            </div>
          </div>

          {/* Per-competition stats */}
          {statistics.length > 0 ? (
            statistics.map((s: any, i: number) => (
              <CompetitionStats key={`${s.league}-${i}`} stats={s} />
            ))
          ) : (
            <p className="text-center text-muted-foreground py-8">
              No stats available for this player
            </p>
          )}

          {/* xG data from Understat */}
          {!xg.isLoading && <XgSection xgData={xgData} />}
        </>
      ) : null}
    </div>
  );
}

function LeaderTable({ entries, type }: { entries: any[]; type: "goals" | "assists" }) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="bg-muted/20 hover:bg-muted/20">
          <TableHead className="h-8 px-3 text-xs w-10">#</TableHead>
          <TableHead className="h-8 px-3 text-xs">Player</TableHead>
          <TableHead className="h-8 px-3 text-xs">Team</TableHead>
          <TableHead className="h-8 px-3 text-xs text-right">{type === "goals" ? "Goals" : "Assists"}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((e: any, i: number) => {
          const parts = (e.value || "").match(/(\d+)$/);
          const num = parts ? parts[1] : e.value;
          return (
            <TableRow key={i} className="border-b border-border/20">
              <TableCell className="px-3 py-1.5 text-sm text-muted-foreground font-bold tabular-nums">{i + 1}</TableCell>
              <TableCell className="px-3 py-1.5 text-sm font-medium">{e.name}</TableCell>
              <TableCell className="px-3 py-1.5 text-sm text-muted-foreground">{e.team_short || e.team}</TableCell>
              <TableCell className="px-3 py-1.5 text-sm text-right font-bold tabular-nums text-fpl-green">{num}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function LeagueLeaders({ league }: { league: any }) {
  return (
    <div className="mb-6">
      <h3 className="text-sm font-display font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        {league.league}
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
              <Trophy className="h-3 w-3 text-fpl-green" />
              Top Scorers
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <LeaderTable entries={league.scorers || []} type="goals" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
              <Trophy className="h-3 w-3 text-fpl-gold" />
              Top Assisters
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <LeaderTable entries={league.assisters || []} type="assists" />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

const LEADER_LEAGUE_ORDER = ["eng.1", "eng.2", "esp.1", "ita.1", "ger.1", "fra.1"];
const LEADER_LEAGUE_SHORT: Record<string, string> = {
  "eng.1": "PL",
  "eng.2": "Champ",
  "esp.1": "La Liga",
  "ita.1": "Serie A",
  "ger.1": "Bundesliga",
  "fra.1": "Ligue 1",
};

function LeadersSection() {
  const leaders = useQuery({
    queryKey: ["leaders"],
    queryFn: () => api.getLeaders(),
  });

  const data = leaders.data as any;
  const allLeagues = data?.leagues ?? [];

  if (leaders.isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-48 w-full" />
        ))}
      </div>
    );
  }

  if (leaders.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Failed to load leaders.</AlertDescription>
      </Alert>
    );
  }

  return (
    <Tabs defaultValue="all">
      <TabsList className="bg-muted/50 mb-4 flex-wrap h-auto gap-1">
        <TabsTrigger value="all" className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm">
          All
        </TabsTrigger>
        {LEADER_LEAGUE_ORDER.filter((slug) =>
          allLeagues.some((l: any) => l.slug === slug),
        ).map((slug) => (
          <TabsTrigger
            key={slug}
            value={slug}
            className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm"
          >
            {LEADER_LEAGUE_SHORT[slug] || slug}
          </TabsTrigger>
        ))}
      </TabsList>

      <TabsContent value="all">
        {LEADER_LEAGUE_ORDER.map((slug) => {
          const lg = allLeagues.find((l: any) => l.slug === slug);
          return lg ? <LeagueLeaders key={slug} league={lg} /> : null;
        })}
      </TabsContent>

      {LEADER_LEAGUE_ORDER.map((slug) => {
        const lg = allLeagues.find((l: any) => l.slug === slug);
        return lg ? (
          <TabsContent key={slug} value={slug}>
            <LeagueLeaders league={lg} />
          </TabsContent>
        ) : null;
      })}
    </Tabs>
  );
}

export default function StatsPage() {
  const [search, setSearch] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPlayer, setSelectedPlayer] = useState<{ id: string; league: string } | null>(null);

  const searchResults = useQuery({
    queryKey: ["playerStatsSearch", searchQuery],
    queryFn: () => api.searchPlayerStats(searchQuery),
    enabled: searchQuery.length >= 2,
  });

  const handleSearch = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && search.trim().length >= 2) {
      setSearchQuery(search.trim());
      setSelectedPlayer(null);
    }
  };

  if (selectedPlayer) {
    return (
      <div>
        <PageHeader title="Player Stats" />
        <PlayerDetail
          playerId={selectedPlayer.id}
          league={selectedPlayer.league}
          onBack={() => setSelectedPlayer(null)}
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Player Stats" />

      <Tabs defaultValue="leaders" className="mb-4">
        <TabsList className="bg-muted/50 mb-4">
          <TabsTrigger value="leaders" className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm">
            Top Scorers & Assisters
          </TabsTrigger>
          <TabsTrigger value="search" className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm">
            Player Search
          </TabsTrigger>
        </TabsList>

        <TabsContent value="leaders">
          <LeadersSection />
        </TabsContent>

        <TabsContent value="search">
          <div className="relative mb-6">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by player name... (press Enter)"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleSearch}
              className="pl-10 pr-10"
            />
            {searchQuery && (
              <button
                onClick={() => { setSearch(""); setSearchQuery(""); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {searchResults.isLoading && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          )}

          {searchResults.isError && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>Search failed.</AlertDescription>
            </Alert>
          )}

          {searchResults.data && (
            <PlayerSearchResults
              results={searchResults.data as any[]}
              onSelect={(p) => setSelectedPlayer({ id: p.id, league: p.league })}
            />
          )}

          {!searchQuery && (
            <div className="text-center py-12 text-muted-foreground">
              <p className="text-lg font-display">Search for a player</p>
              <p className="text-sm mt-1">View detailed stats across any European league</p>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
