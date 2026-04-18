import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAutoRefreshInterval } from "@/hooks/use-auto-refresh";
import PageHeader from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { RotateCw, Circle, Trophy, Shield, Zap, HandMetal } from "lucide-react";

function StatusBadge({ status, kickoff, matchMinute }: { status: string; kickoff: string | null; matchMinute?: number }) {
  if (status === "in") {
    return (
      <Badge className="bg-fpl-green/15 text-fpl-green border border-fpl-green/30 text-xs animate-pulse-glow">
        <Circle className="h-2 w-2 mr-1 fill-fpl-green" />
        LIVE{matchMinute && matchMinute > 0 ? ` · ${matchMinute}'` : ""}
      </Badge>
    );
  }
  if (status === "finished") {
    return <Badge variant="outline" className="text-xs">FT</Badge>;
  }
  // scheduled
  const kickoffTime = kickoff
    ? new Date(kickoff).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";
  return (
    <Badge variant="outline" className="text-xs text-muted-foreground">
      {kickoffTime || "Not Started"}
    </Badge>
  );
}

function FixtureCard({ fixture }: { fixture: any }) {
  const isLive = fixture.status === "in";
  const hasStarted = fixture.status !== "scheduled";
  const homeShort = fixture.home_team_short;
  const awayShort = fixture.away_team_short;

  const homeGoals = (fixture.goal_scorers || []).filter((g: any) => g.team === homeShort);
  const awayGoals = (fixture.goal_scorers || []).filter((g: any) => g.team === awayShort);
  const homeAssists = (fixture.assisters || []).filter((a: any) => a.team === homeShort);
  const awayAssists = (fixture.assisters || []).filter((a: any) => a.team === awayShort);

  return (
    <Card className={`mb-3 overflow-hidden ${isLive ? "border-fpl-green/30" : ""}`}>
      <CardContent className="p-4">
        {/* Status */}
        <div className="flex items-center justify-between mb-3">
          <StatusBadge status={fixture.status} kickoff={fixture.kickoff_time} matchMinute={fixture.match_minute} />
        </div>

        {/* Score line */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold flex-1">{fixture.home_team}</span>
          <div className="px-4 text-center min-w-[60px]">
            {hasStarted ? (
              <span className={`text-xl font-display font-bold tabular-nums ${isLive ? "text-fpl-green" : ""}`}>
                {fixture.home_score ?? 0} - {fixture.away_score ?? 0}
              </span>
            ) : (
              <span className="text-lg font-display text-muted-foreground">vs</span>
            )}
          </div>
          <span className="text-sm font-semibold flex-1 text-right">{fixture.away_team}</span>
        </div>

        {/* Goals + Assists */}
        {(homeGoals.length > 0 || awayGoals.length > 0) && (
          <div className="mt-3 pt-2 border-t border-border/30">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Trophy className="h-3 w-3 text-fpl-green" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Goals</span>
            </div>
            <div className="flex justify-between gap-4 text-xs">
              <div className="flex-1 space-y-0.5">
                {homeGoals.map((g: any, i: number) => (
                  <div key={i} className="text-fpl-green font-medium">{g.player}</div>
                ))}
              </div>
              <div className="flex-1 space-y-0.5 text-right">
                {awayGoals.map((g: any, i: number) => (
                  <div key={i} className="text-fpl-green font-medium">{g.player}</div>
                ))}
              </div>
            </div>
          </div>
        )}

        {(homeAssists.length > 0 || awayAssists.length > 0) && (
          <div className="mt-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Assists</span>
            <div className="flex justify-between gap-4 text-xs mt-0.5">
              <div className="flex-1 space-y-0.5">
                {homeAssists.map((a: any, i: number) => (
                  <div key={i} className="text-muted-foreground">{a.player}</div>
                ))}
              </div>
              <div className="flex-1 space-y-0.5 text-right">
                {awayAssists.map((a: any, i: number) => (
                  <div key={i} className="text-muted-foreground">{a.player}</div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* GK Saves */}
        {fixture.gk_saves && fixture.gk_saves.length > 0 && (
          <div className="mt-2">
            <div className="flex items-center gap-1.5 mb-1.5">
              <HandMetal className="h-3 w-3 text-muted-foreground" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Saves</span>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {fixture.gk_saves.map((s: any, i: number) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="font-medium">{s.player}</span>
                  <span className="text-[10px] text-muted-foreground">{s.team}</span>
                  <span className="tabular-nums font-semibold">{s.saves}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top BPS */}
        {fixture.top_bps && fixture.top_bps.length > 0 && (
          <div className="mt-3 pt-2 border-t border-border/30">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Zap className="h-3 w-3 text-fpl-gold" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Bonus Points</span>
            </div>
            <div className="space-y-1">
              {fixture.top_bps.map((b: any, i: number) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground tabular-nums w-3">{i + 1}</span>
                    <span className="font-medium">{b.player}</span>
                    <span className="text-[10px] text-muted-foreground">{b.team} · {b.position}</span>
                  </div>
                  <div className="flex items-center gap-2 tabular-nums">
                    <span className="text-muted-foreground">{b.bps} BPS</span>
                    {b.bonus > 0 && (
                      <span className="text-fpl-gold font-semibold">+{b.bonus}</span>
                    )}
                    <span className="font-bold text-fpl-green">{b.points}pt</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top DEFCON */}
        {fixture.top_defcon && fixture.top_defcon.length > 0 && (
          <div className="mt-3 pt-2 border-t border-border/30">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Shield className="h-3 w-3 text-muted-foreground" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">DEFCON</span>
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
              {fixture.top_defcon.map((d: any, i: number) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="font-medium">{d.player}</span>
                  <span className="text-[10px] text-muted-foreground">{d.team}</span>
                  <span className="tabular-nums font-semibold">{d.defcon}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function LiveGameweekPage() {
  const qc = useQueryClient();
  const refetchInterval = useAutoRefreshInterval();

  const live = useQuery({
    queryKey: ["liveGameweek"],
    queryFn: () => api.getLiveGameweek(),
    refetchInterval,
    refetchIntervalInBackground: true,
  });

  const data = live.data as any;
  const fixtures = data?.fixtures ?? [];
  const cachedAt = data?.fetched_at || live.dataUpdatedAt;
  const lastUpdated = cachedAt
    ? new Date(typeof cachedAt === "string" ? cachedAt : cachedAt).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : null;

  return (
    <div>
      <PageHeader
        title={`Live Gameweek${data?.gameweek ? ` ${data.gameweek}` : ""}`}
        actions={
          <div className="flex items-center gap-2">
            {refetchInterval && (
              <span className="flex items-center gap-1 text-xs text-fpl-green">
                <span className="h-2 w-2 rounded-full bg-fpl-green animate-pulse" />
                Auto-updating
              </span>
            )}
            {lastUpdated && (
              <span className="text-[10px] text-muted-foreground">{lastUpdated}</span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => qc.invalidateQueries({ queryKey: ["liveGameweek"] })}
              disabled={live.isFetching}
            >
              <RotateCw className={`h-4 w-4 mr-1 ${live.isFetching ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        }
      />

      {live.isError && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>Failed to load live gameweek data.</AlertDescription>
        </Alert>
      )}

      {live.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : fixtures.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p className="text-lg font-display">No fixtures this gameweek</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {fixtures.map((f: any) => (
            <FixtureCard key={f.fixture_id} fixture={f} />
          ))}
        </div>
      )}
    </div>
  );
}
