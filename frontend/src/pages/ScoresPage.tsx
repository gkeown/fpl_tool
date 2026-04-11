import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { RotateCw, Circle } from "lucide-react";

const LEAGUE_ORDER = [39, 135, 140, 78, 61];
const LEAGUE_SHORT: Record<number, string> = {
  39: "PL",
  135: "Serie A",
  140: "La Liga",
  78: "Bundesliga",
  61: "Ligue 1",
};

function StatusBadge({ status, elapsed }: { status: string; elapsed: number | null }) {
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

function MatchCard({ match }: { match: any }) {
  const isLive = ["1H", "2H", "ET"].includes(match.status);
  const hasStarted = match.status !== "NS" && match.status !== "TBD";
  const kickoffTime = match.kickoff
    ? new Date(match.kickoff).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

  const goalEvents = (match.events || []).filter((e: any) => e.type === "Goal");

  return (
    <Card className={`mb-2 overflow-hidden ${isLive ? "border-fpl-green/30" : ""}`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <StatusBadge status={match.status} elapsed={match.elapsed} />
          {!hasStarted && kickoffTime && (
            <span className="text-xs text-muted-foreground">{kickoffTime}</span>
          )}
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

        {/* Goal scorers */}
        {goalEvents.length > 0 && (
          <div className="mt-3 pt-2 border-t border-border/30 space-y-1">
            {goalEvents.map((e: any, i: number) => {
              const minuteStr = e.extra_minute
                ? `${e.minute}+${e.extra_minute}'`
                : `${e.minute}'`;
              const isPenalty = e.detail === "Penalty";
              const isOwnGoal = e.detail === "Own Goal";
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="text-muted-foreground tabular-nums w-10">{minuteStr}</span>
                  <span className="text-fpl-green font-medium">
                    {e.player}
                    {isPenalty && <span className="text-muted-foreground ml-1">(pen)</span>}
                    {isOwnGoal && <span className="text-fpl-pink ml-1">(og)</span>}
                  </span>
                  {e.assist && (
                    <span className="text-muted-foreground">
                      ast. {e.assist}
                    </span>
                  )}
                </div>
              );
            })}
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

  const scores = useQuery({
    queryKey: ["todayScores"],
    queryFn: () => api.getTodayScores(),
  });

  const data = scores.data as any;
  const allLeagues = data?.leagues ?? [];

  return (
    <div>
      <PageHeader
        title="Live Scores"
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => qc.invalidateQueries({ queryKey: ["todayScores"] })}
            disabled={scores.isFetching}
          >
            <RotateCw className={`h-4 w-4 mr-1 ${scores.isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      {scores.isError && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>
            Failed to load scores. Check that FPL_API_FOOTBALL_KEY is set in .env.
          </AlertDescription>
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
