import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAutoRefresh, useAutoRefreshInterval } from "@/hooks/use-auto-refresh";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { RotateCw, Circle } from "lucide-react";

const LEAGUE_ORDER = ["eng.1", "eng.2", "sco.1", "ita.1", "esp.1", "ger.1", "fra.1"];
const LEAGUE_SHORT: Record<string, string> = {
  "eng.1": "PL",
  "eng.2": "Championship",
  "sco.1": "SPL",
  "ita.1": "Serie A",
  "esp.1": "La Liga",
  "ger.1": "Bundesliga",
  "fra.1": "Ligue 1",
};

const ZONE_COLORS: Record<string, string> = {
  "Champions League": "border-l-2 border-l-blue-500",
  "UEFA Champions League": "border-l-2 border-l-blue-500",
  "Europa League": "border-l-2 border-l-orange-500",
  "UEFA Europa League": "border-l-2 border-l-orange-500",
  "Conference League": "border-l-2 border-l-green-600",
  "UEFA Europa Conference League": "border-l-2 border-l-green-600",
  "Relegation": "border-l-2 border-l-fpl-pink",
  "Promotion": "border-l-2 border-l-fpl-green",
  "Promotion - Championship": "border-l-2 border-l-fpl-green",
  "Playoff": "border-l-2 border-l-fpl-gold",
  "Promotion Playoff": "border-l-2 border-l-fpl-gold",
};

function getZoneClass(zone: string): string {
  for (const [key, cls] of Object.entries(ZONE_COLORS)) {
    if (zone.toLowerCase().includes(key.toLowerCase())) return cls;
  }
  return "";
}

function LeagueTable({ table }: { table: any[] }) {
  return (
    <div className="rounded-lg border overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-muted/30">
            <th className="text-left px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground w-10">#</th>
            <th className="text-left px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Team</th>
            <th className="text-center px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground w-10">P</th>
            <th className="text-center px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground w-10">W</th>
            <th className="text-center px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground w-10">D</th>
            <th className="text-center px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground w-10">L</th>
            <th className="text-center px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground w-10">GF</th>
            <th className="text-center px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground w-10">GA</th>
            <th className="text-center px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground w-10">GD</th>
            <th className="text-center px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground w-12">Pts</th>
          </tr>
        </thead>
        <tbody>
          {table.map((row: any) => {
            const zoneClass = getZoneClass(row.zone || "");
            return (
              <tr
                key={row.position}
                className={`border-t border-border/20 ${zoneClass} ${row.live ? "bg-fpl-green/5" : ""}`}
              >
                <td className="px-3 py-1.5 text-sm font-bold text-muted-foreground tabular-nums">{row.position}</td>
                <td className="px-3 py-1.5 text-sm font-medium">
                  <div className="flex items-center gap-1.5">
                    {row.live && (
                      <span className="h-1.5 w-1.5 rounded-full bg-fpl-green animate-pulse" title="Live" />
                    )}
                    {row.team}
                  </div>
                </td>
                <td className="text-center px-2 py-1.5 text-sm tabular-nums">{row.played}</td>
                <td className="text-center px-2 py-1.5 text-sm tabular-nums">{row.won}</td>
                <td className="text-center px-2 py-1.5 text-sm tabular-nums">{row.drawn}</td>
                <td className="text-center px-2 py-1.5 text-sm tabular-nums">{row.lost}</td>
                <td className="text-center px-2 py-1.5 text-sm tabular-nums">{row.gf}</td>
                <td className="text-center px-2 py-1.5 text-sm tabular-nums">{row.ga}</td>
                <td className="text-center px-2 py-1.5 text-sm tabular-nums font-medium">
                  <span className={row.gd > 0 ? "text-fpl-green" : row.gd < 0 ? "text-fpl-pink" : ""}>
                    {row.gd > 0 ? `+${row.gd}` : row.gd}
                  </span>
                </td>
                <td className="text-center px-2 py-1.5 text-sm font-bold tabular-nums">{row.points}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function TablesPage() {
  const qc = useQueryClient();
  const autoRefresh = useAutoRefresh();
  const refetchInterval = useAutoRefreshInterval();

  const standings = useQuery({
    queryKey: ["standings"],
    queryFn: () => api.getStandings(),
    refetchInterval,
    refetchIntervalInBackground: true,
  });

  const data = standings.data as any;
  const allLeagues = data?.leagues ?? [];
  const cachedAt = data?.cached_at;
  const lastUpdated = cachedAt
    ? new Date(cachedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : null;

  return (
    <div>
      <PageHeader
        title="Tables"
        actions={
          <div className="flex items-center gap-2">
            {autoRefresh && (
              <span className="flex items-center gap-1 text-xs text-fpl-green">
                <Circle className="h-2 w-2 fill-fpl-green animate-pulse" />
                Auto-updating
              </span>
            )}
            {lastUpdated && (
              <span className="text-[10px] text-muted-foreground">{lastUpdated}</span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => qc.invalidateQueries({ queryKey: ["standings"] })}
              disabled={standings.isFetching}
            >
              <RotateCw className={`h-4 w-4 mr-1 ${standings.isFetching ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        }
      />

      {standings.isError && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>Failed to load standings.</AlertDescription>
        </Alert>
      )}

      {standings.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-64 w-full" />
          ))}
        </div>
      ) : allLeagues.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p className="text-lg font-display">No standings available</p>
        </div>
      ) : (
        <Tabs defaultValue="eng.1">
          <TabsList className="bg-muted/50 mb-4 flex-wrap h-auto gap-1">
            {LEAGUE_ORDER.filter((lid) => allLeagues.some((l: any) => l.id === lid)).map((lid) => (
              <TabsTrigger
                key={lid}
                value={lid}
                className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm"
              >
                {LEAGUE_SHORT[lid]}
              </TabsTrigger>
            ))}
          </TabsList>

          {LEAGUE_ORDER.map((lid) => {
            const league = allLeagues.find((l: any) => l.id === lid);
            return league ? (
              <TabsContent key={lid} value={lid}>
                <h3 className="text-sm font-display font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                  {league.name}
                </h3>
                <LeagueTable table={league.table} />
              </TabsContent>
            ) : null;
          })}
        </Tabs>
      )}
    </div>
  );
}
