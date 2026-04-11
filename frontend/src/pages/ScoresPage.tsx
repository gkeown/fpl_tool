import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAutoRefresh, useAutoRefreshInterval } from "@/hooks/use-auto-refresh";
import PageHeader from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { RotateCw, Circle } from "lucide-react";

const LEAGUE_ORDER = ["eng.1", "ita.1", "esp.1", "ger.1", "fra.1"];
const LEAGUE_SHORT: Record<string, string> = {
  "eng.1": "PL",
  "ita.1": "Serie A",
  "esp.1": "La Liga",
  "ger.1": "Bundesliga",
  "fra.1": "Ligue 1",
};

function MatchStatusBadge({ status, elapsed }: { status: string; elapsed: number | null }) {
  if (status === "NS" || status === "TBD") {
    return <Badge variant="outline" className="text-xs text-muted-foreground">Not Started</Badge>;
  }
  if (status === "FT" || status === "AET" || status === "PEN") {
    return <Badge variant="outline" className="text-xs">FT</Badge>;
  }
  if (status === "HT") {
    return <Badge className="bg-fpl-gold/15 text-fpl-gold border border-fpl-gold/30 text-xs">HT</Badge>;
  }
  if (status === "1H" || status === "2H" || status === "ET") {
    return (
      <Badge className="bg-fpl-green/15 text-fpl-green border border-fpl-green/30 text-xs animate-pulse-glow">
        <Circle className="h-2 w-2 mr-1 fill-fpl-green" />
        {elapsed ? `${elapsed}'` : "LIVE"}
      </Badge>
    );
  }
  if (status === "PST") {
    return <Badge variant="outline" className="text-xs text-fpl-pink">Postponed</Badge>;
  }
  return <Badge variant="outline" className="text-xs">{status}</Badge>;
}

function GoalList({ goals, align }: { goals: any[]; align: "left" | "right" }) {
  if (goals.length === 0) return null;
  return (
    <div className={`space-y-0.5 ${align === "right" ? "text-right" : "text-left"}`}>
      {goals.map((e: any, i: number) => {
        const minuteStr = e.extra_minute ? `${e.minute}+${e.extra_minute}'` : `${e.minute}'` || "";
        const isPenalty = e.detail === "Penalty" || e.detail === "Penalty - Scored";
        const isOwnGoal = e.detail === "Own Goal";
        return (
          <div key={i} className={`text-xs flex items-center gap-1.5 ${align === "right" ? "justify-end" : ""}`}>
            {align === "left" && <span className="text-muted-foreground tabular-nums">{minuteStr}</span>}
            <span className="text-fpl-green font-medium">
              {e.player}
              {isPenalty && <span className="text-muted-foreground ml-1">(pen)</span>}
              {isOwnGoal && <span className="text-fpl-pink ml-1">(og)</span>}
            </span>
            {e.assist && <span className="text-muted-foreground">({e.assist})</span>}
            {align === "right" && <span className="text-muted-foreground tabular-nums">{minuteStr}</span>}
          </div>
        );
      })}
    </div>
  );
}

function RedCardList({ cards, align }: { cards: any[]; align: "left" | "right" }) {
  if (cards.length === 0) return null;
  return (
    <div className={`space-y-0.5 ${align === "right" ? "text-right" : "text-left"}`}>
      {cards.map((e: any, i: number) => {
        const minuteStr = e.minute || "";
        return (
          <div key={i} className={`text-xs flex items-center gap-1.5 ${align === "right" ? "justify-end" : ""}`}>
            {align === "left" && <span className="text-muted-foreground tabular-nums">{minuteStr}</span>}
            <span className="text-fpl-pink font-medium">
              {e.player}
              {e.detail === "Second Yellow" && <span className="text-muted-foreground ml-1">(2nd yellow)</span>}
            </span>
            <span className="text-fpl-pink">&#x1F7E5;</span>
            {align === "right" && <span className="text-muted-foreground tabular-nums">{minuteStr}</span>}
          </div>
        );
      })}
    </div>
  );
}

function MatchCard({ match }: { match: any }) {
  const isLive = ["1H", "2H", "ET"].includes(match.status);
  const hasStarted = match.status !== "NS" && match.status !== "TBD";
  const kickoffTime = match.kickoff
    ? new Date(match.kickoff).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";
  const matchDate = match.kickoff
    ? new Date(match.kickoff).toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" })
    : "";

  const allEvents = match.events || [];
  const goalEvents = allEvents.filter((e: any) => e.type === "Goal");
  const redCards = allEvents.filter((e: any) => e.type === "Red Card");
  const homeGoals = goalEvents.filter((e: any) => e.team === match.home_team);
  const awayGoals = goalEvents.filter((e: any) => e.team === match.away_team);
  const homeReds = redCards.filter((e: any) => e.team === match.home_team);
  const awayReds = redCards.filter((e: any) => e.team === match.away_team);

  return (
    <Card className={`mb-2 overflow-hidden ${isLive ? "border-fpl-green/30" : ""}`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <MatchStatusBadge status={match.status} elapsed={match.elapsed} />
          <span className="text-xs text-muted-foreground">
            {!hasStarted && kickoffTime ? `${matchDate} ${kickoffTime}` : matchDate}
          </span>
        </div>

        {/* Score line */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold flex-1">{match.home_team}</span>
          <div className="px-4 text-center min-w-[60px]">
            {hasStarted ? (
              <span className={`text-xl font-display font-bold tabular-nums ${isLive ? "text-fpl-green" : ""}`}>
                {match.home_goals ?? 0} - {match.away_goals ?? 0}
              </span>
            ) : (
              <span className="text-lg font-display text-muted-foreground">vs</span>
            )}
          </div>
          <span className="text-sm font-semibold flex-1 text-right">{match.away_team}</span>
        </div>

        {/* Goal scorers split by team */}
        {goalEvents.length > 0 && (
          <div className="mt-3 pt-2 border-t border-border/30">
            <div className="flex justify-between gap-4">
              <div className="flex-1">
                <GoalList goals={homeGoals} align="left" />
              </div>
              <div className="flex-1">
                <GoalList goals={awayGoals} align="right" />
              </div>
            </div>
          </div>
        )}

        {/* Red cards split by team */}
        {redCards.length > 0 && (
          <div className={`${goalEvents.length > 0 ? "mt-2" : "mt-3 pt-2 border-t border-border/30"}`}>
            <div className="flex justify-between gap-4">
              <div className="flex-1">
                <RedCardList cards={homeReds} align="left" />
              </div>
              <div className="flex-1">
                <RedCardList cards={awayReds} align="right" />
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function LeagueSection({ league }: { league: any }) {
  return (
    <div className="mb-6">
      <h3 className="text-sm font-display font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        {league.name}
      </h3>
      {league.matches.map((m: any) => (
        <MatchCard key={m.fixture_id} match={m} />
      ))}
    </div>
  );
}

export default function ScoresPage() {
  const qc = useQueryClient();
  const autoRefresh = useAutoRefresh();
  const refetchInterval = useAutoRefreshInterval();

  const scores = useQuery({
    queryKey: ["todayScores"],
    queryFn: () => api.getTodayScores(),
    refetchInterval,
  });

  const data = scores.data as any;
  const allLeagues = data?.leagues ?? [];
  const cachedAt = data?.cached_at;
  const lastUpdated = cachedAt
    ? new Date(cachedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : null;

  return (
    <div>
      <PageHeader
        title="Live Scores"
        actions={
          <div className="flex items-center gap-2">
            {autoRefresh && (
              <span className="flex items-center gap-1 text-xs text-fpl-green">
                <Circle className="h-2 w-2 fill-fpl-green animate-pulse" />
                Auto-updating
              </span>
            )}
            {lastUpdated && (
              <span className="text-[10px] text-muted-foreground">
                {lastUpdated}
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => qc.invalidateQueries({ queryKey: ["todayScores"] })}
              disabled={scores.isFetching}
            >
              <RotateCw className={`h-4 w-4 mr-1 ${scores.isFetching ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        }
      />

      {scores.isError && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>Failed to load scores.</AlertDescription>
        </Alert>
      )}

      {scores.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : allLeagues.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p className="text-lg font-display">No matches today</p>
          <p className="text-sm mt-1">Check back on match days</p>
        </div>
      ) : (
        <Tabs defaultValue="all">
          <TabsList className="bg-muted/50 mb-4 flex-wrap h-auto gap-1">
            <TabsTrigger
              value="all"
              className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm"
            >
              All
            </TabsTrigger>
            {LEAGUE_ORDER.filter((lid) => allLeagues.some((l: any) => l.id === lid)).map((lid) => (
              <TabsTrigger
                key={lid}
                value={String(lid)}
                className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm"
              >
                {LEAGUE_SHORT[lid]}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="all">
            {LEAGUE_ORDER.map((lid) => {
              const league = allLeagues.find((l: any) => l.id === lid);
              return league ? <LeagueSection key={lid} league={league} /> : null;
            })}
          </TabsContent>

          {LEAGUE_ORDER.map((lid) => {
            const league = allLeagues.find((l: any) => l.id === lid);
            return league ? (
              <TabsContent key={lid} value={String(lid)}>
                <LeagueSection league={league} />
              </TabsContent>
            ) : null;
          })}
        </Tabs>
      )}
    </div>
  );
}
