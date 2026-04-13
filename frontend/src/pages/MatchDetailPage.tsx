import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAutoRefreshInterval } from "@/hooks/use-auto-refresh";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ArrowLeft, Circle } from "lucide-react";

// Map stat name -> friendly label + format
const STAT_LABELS: Record<string, { label: string; isPercent?: boolean }> = {
  possessionPct: { label: "Possession", isPercent: true },
  totalShots: { label: "Shots" },
  shotsOnTarget: { label: "Shots on Target" },
  blockedShots: { label: "Blocked Shots" },
  wonCorners: { label: "Corners" },
  offsides: { label: "Offsides" },
  foulsCommitted: { label: "Fouls" },
  yellowCards: { label: "Yellow Cards" },
  redCards: { label: "Red Cards" },
  saves: { label: "Saves" },
  accuratePasses: { label: "Accurate Passes" },
  totalPasses: { label: "Total Passes" },
  passPct: { label: "Pass Accuracy", isPercent: true },
  accurateCrosses: { label: "Accurate Crosses" },
  totalCrosses: { label: "Total Crosses" },
  crossPct: { label: "Cross Accuracy", isPercent: true },
  totalLongBalls: { label: "Long Balls" },
  accurateLongBalls: { label: "Accurate Long Balls" },
  longballPct: { label: "Long Ball Accuracy", isPercent: true },
  effectiveTackles: { label: "Tackles Won" },
  totalTackles: { label: "Total Tackles" },
  tacklePct: { label: "Tackle Success", isPercent: true },
  interceptions: { label: "Interceptions" },
  effectiveClearance: { label: "Clearances" },
  penaltyKickGoals: { label: "Penalty Goals" },
  penaltyKickShots: { label: "Penalty Shots" },
};

const STAT_ORDER = [
  "possessionPct",
  "totalShots",
  "shotsOnTarget",
  "blockedShots",
  "wonCorners",
  "offsides",
  "foulsCommitted",
  "yellowCards",
  "redCards",
  "saves",
  "accuratePasses",
  "totalPasses",
  "passPct",
  "accurateCrosses",
  "totalCrosses",
  "totalLongBalls",
  "accurateLongBalls",
  "effectiveTackles",
  "totalTackles",
  "interceptions",
  "effectiveClearance",
];

function parseNumeric(val: string | undefined): number {
  if (!val) return 0;
  const n = parseFloat(val.replace("%", ""));
  return isNaN(n) ? 0 : n;
}

function StatRow({
  name,
  homeVal,
  awayVal,
}: {
  name: string;
  homeVal: string;
  awayVal: string;
}) {
  const cfg = STAT_LABELS[name] || { label: name };
  const homeNum = parseNumeric(homeVal);
  const awayNum = parseNumeric(awayVal);
  const total = homeNum + awayNum;
  const homePct = total > 0 ? (homeNum / total) * 100 : 50;
  const awayPct = total > 0 ? (awayNum / total) * 100 : 50;

  const homeDisplay = cfg.isPercent
    ? `${Math.round(homeNum)}%`
    : homeVal;
  const awayDisplay = cfg.isPercent
    ? `${Math.round(awayNum)}%`
    : awayVal;

  return (
    <div className="py-2">
      <div className="flex items-center justify-between mb-1 text-sm">
        <span className="font-semibold tabular-nums w-12 text-left">{homeDisplay}</span>
        <span className="text-xs text-muted-foreground uppercase tracking-wider">
          {cfg.label}
        </span>
        <span className="font-semibold tabular-nums w-12 text-right">{awayDisplay}</span>
      </div>
      <div className="flex h-1.5 rounded-full overflow-hidden bg-muted">
        <div
          className="bg-fpl-green"
          style={{ width: `${homePct}%` }}
        />
        <div
          className="bg-fpl-pink"
          style={{ width: `${awayPct}%` }}
        />
      </div>
    </div>
  );
}

function LineupColumn({
  roster,
  side,
}: {
  roster: any;
  side: "home" | "away";
}) {
  if (!roster) return null;
  const starters = roster.starters || [];
  const subs = roster.subs || [];
  return (
    <div>
      <h3 className={`text-sm font-display font-semibold uppercase tracking-wider mb-2 ${side === "away" ? "text-right" : ""}`}>
        {roster.team}
      </h3>
      <Card className="mb-3">
        <CardHeader className="py-2 px-3">
          <CardTitle className="text-[10px] font-sans font-semibold uppercase tracking-widest text-muted-foreground">
            Starting XI
          </CardTitle>
        </CardHeader>
        <CardContent className="px-3 pb-3 space-y-1">
          {starters.map((p: any, i: number) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground tabular-nums w-5">{p.jersey}</span>
              <span className="font-medium truncate">{p.name}</span>
              {p.position && (
                <span className="text-[10px] text-muted-foreground ml-auto">{p.position}</span>
              )}
            </div>
          ))}
          {starters.length === 0 && (
            <p className="text-xs text-muted-foreground">Lineup not yet available</p>
          )}
        </CardContent>
      </Card>
      {subs.length > 0 && (
        <Card>
          <CardHeader className="py-2 px-3">
            <CardTitle className="text-[10px] font-sans font-semibold uppercase tracking-widest text-muted-foreground">
              Bench
            </CardTitle>
          </CardHeader>
          <CardContent className="px-3 pb-3 space-y-1">
            {subs.map((p: any, i: number) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground tabular-nums w-5">{p.jersey}</span>
                <span className="font-medium truncate">{p.name}</span>
                {p.position && (
                  <span className="text-[10px] text-muted-foreground ml-auto">{p.position}</span>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function MatchDetailPage() {
  const { leagueSlug, fixtureId } = useParams<{
    leagueSlug: string;
    fixtureId: string;
  }>();
  const navigate = useNavigate();
  const refetchInterval = useAutoRefreshInterval(30_000);

  const match = useQuery({
    queryKey: ["matchDetail", leagueSlug, fixtureId],
    queryFn: () =>
      api.getMatchDetail(leagueSlug || "eng.1", fixtureId || ""),
    enabled: !!fixtureId,
    refetchInterval,
    refetchIntervalInBackground: true,
  });

  const data = match.data as any;
  const isLive = data?.status?.state === "in";

  if (match.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (match.isError || !data) {
    return (
      <div>
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="mb-4 -ml-2">
          <ArrowLeft className="h-4 w-4 mr-1" /> Back
        </Button>
        <Alert variant="destructive">
          <AlertDescription>Failed to load match details.</AlertDescription>
        </Alert>
      </div>
    );
  }

  const homeStats = data.home?.stats || {};
  const awayStats = data.away?.stats || {};
  const hasStats = Object.keys(homeStats).length > 0;

  return (
    <div>
      <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="mb-4 -ml-2">
        <ArrowLeft className="h-4 w-4 mr-1" /> Back to Scores
      </Button>

      {/* Match header */}
      <Card className={`mb-4 ${isLive ? "border-fpl-green/30" : ""}`}>
        <CardContent className="p-5">
          <div className="flex items-center justify-between mb-3">
            {isLive ? (
              <Badge className="bg-fpl-green/15 text-fpl-green border border-fpl-green/30 text-xs animate-pulse-glow">
                <Circle className="h-2 w-2 mr-1 fill-fpl-green" />
                LIVE {data.status.display_clock}
              </Badge>
            ) : data.status.state === "post" ? (
              <Badge variant="outline" className="text-xs">FT</Badge>
            ) : (
              <Badge variant="outline" className="text-xs text-muted-foreground">
                {data.status.description || "Scheduled"}
              </Badge>
            )}
            {data.venue && (
              <span className="text-xs text-muted-foreground">{data.venue}</span>
            )}
          </div>

          <div className="flex items-center justify-between">
            <div className="flex-1 text-center">
              {data.home.logo && (
                <img
                  src={data.home.logo}
                  alt={data.home.name}
                  className="h-12 w-12 mx-auto mb-1"
                />
              )}
              <p className="text-sm font-semibold">{data.home.name}</p>
            </div>
            <div className="px-6 text-center">
              <div className="text-4xl font-display font-bold tabular-nums">
                {data.home.score} - {data.away.score}
              </div>
            </div>
            <div className="flex-1 text-center">
              {data.away.logo && (
                <img
                  src={data.away.logo}
                  alt={data.away.name}
                  className="h-12 w-12 mx-auto mb-1"
                />
              )}
              <p className="text-sm font-semibold">{data.away.name}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="stats">
        <TabsList className="bg-muted/50 mb-4">
          <TabsTrigger
            value="stats"
            className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm"
          >
            Stats
          </TabsTrigger>
          <TabsTrigger
            value="lineups"
            className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm"
          >
            Lineups
          </TabsTrigger>
          <TabsTrigger
            value="events"
            className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm"
          >
            Events
          </TabsTrigger>
        </TabsList>

        <TabsContent value="stats">
          {!hasStats ? (
            <p className="text-center text-muted-foreground py-8">
              Stats not yet available
            </p>
          ) : (
            <Card>
              <CardContent className="p-4 divide-y divide-border/30">
                {STAT_ORDER.filter(
                  (name) => homeStats[name] || awayStats[name],
                ).map((name) => (
                  <StatRow
                    key={name}
                    name={name}
                    homeVal={homeStats[name] || "0"}
                    awayVal={awayStats[name] || "0"}
                  />
                ))}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="lineups">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <LineupColumn roster={data.home.roster} side="home" />
            <LineupColumn roster={data.away.roster} side="away" />
          </div>
        </TabsContent>

        <TabsContent value="events">
          {data.events && data.events.length > 0 ? (
            <Card>
              <CardContent className="p-4 space-y-2">
                {data.events.map((ev: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 text-sm py-1.5 border-b border-border/20 last:border-0"
                  >
                    <span className="text-muted-foreground tabular-nums w-12 font-semibold">
                      {ev.minute || "-"}
                    </span>
                    <span className={ev.scoring_play ? "text-fpl-green font-medium" : ""}>
                      {ev.text}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : (
            <p className="text-center text-muted-foreground py-8">
              No events yet
            </p>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
