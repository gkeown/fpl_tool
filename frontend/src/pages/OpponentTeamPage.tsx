import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAutoRefreshInterval } from "@/hooks/use-auto-refresh";
import PageHeader from "@/components/PageHeader";
import FormBadge from "@/components/FormBadge";
import StatusBadge from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, ArrowRight, Zap } from "lucide-react";

const CHIP_LABELS: Record<string, string> = {
  wildcard: "Wildcard",
  freehit: "Free Hit",
  bboost: "Bench Boost",
  "3xc": "Triple Captain",
  manager: "Assistant Manager",
};

function PlayerTable({ players, title, dimmed }: { players: any[]; title: string; dimmed?: boolean }) {
  return (
    <Card className={`mb-4 ${dimmed ? "opacity-70" : ""}`}>
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-sm font-sans font-semibold uppercase tracking-widest text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-border/50 bg-muted/20 hover:bg-muted/20">
              <TableHead className="h-8 px-3 text-xs">Pos</TableHead>
              <TableHead className="h-8 px-3 text-xs">Player</TableHead>
              <TableHead className="h-8 px-3 text-xs">Team</TableHead>
              <TableHead className="h-8 px-3 text-xs text-right">Cost</TableHead>
              <TableHead className="h-8 px-3 text-xs text-right">Form</TableHead>
              <TableHead className="h-8 px-3 text-xs text-right">GW Pts</TableHead>
              <TableHead className="h-8 px-3 text-xs text-right">Bonus</TableHead>
              <TableHead className="h-8 px-3 text-xs text-right">DEFCON</TableHead>
              <TableHead className="h-8 px-3 text-xs text-center">Opponent</TableHead>
              <TableHead className="h-8 px-3 text-xs text-center">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {players.map((p: any) => (
              <TableRow
                key={p.id}
                className={`border-b border-border/20 ${p.is_captain ? "bg-fpl-green/5" : ""} ${p.is_playing ? "border-l-2 border-l-fpl-green" : ""}`}
              >
                <TableCell className="px-3 py-1.5 text-sm">{p.position}</TableCell>
                <TableCell className="px-3 py-1.5 text-sm">
                  <div className="flex items-center gap-1.5">
                    {p.is_playing && (
                      <span className="h-1.5 w-1.5 rounded-full bg-fpl-green animate-pulse" title="Playing" />
                    )}
                    <span className="font-medium">{p.web_name}</span>
                    {p.is_captain && (
                      <span className="inline-flex items-center justify-center h-4 w-4 rounded-full bg-fpl-green text-[9px] font-bold text-black">C</span>
                    )}
                    {p.is_vice_captain && (
                      <span className="inline-flex items-center justify-center h-4 w-4 rounded-full bg-muted text-[9px] font-bold">V</span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="px-3 py-1.5 text-sm text-muted-foreground">{p.team}</TableCell>
                <TableCell className="px-3 py-1.5 text-sm text-right tabular-nums">{'\u00A3'}{p.cost?.toFixed(1)}m</TableCell>
                <TableCell className="px-3 py-1.5 text-right">
                  <FormBadge value={p.form || 0} />
                </TableCell>
                <TableCell className="px-3 py-1.5 text-sm text-right tabular-nums">
                  <span className={`font-semibold ${((p.gw_points || p.event_points || 0)) >= 8 ? "text-fpl-green" : ""}`}>
                    {p.gw_points || p.event_points || 0}
                  </span>
                </TableCell>
                <TableCell className="px-3 py-1.5 text-sm text-right tabular-nums">
                  <span className={(p.gw_bonus || 0) >= 3 ? "text-fpl-gold font-semibold" : ""}>
                    {p.gw_bonus ?? 0}
                  </span>
                </TableCell>
                <TableCell className="px-3 py-1.5 text-sm text-right tabular-nums text-muted-foreground">{p.defcon ?? 0}</TableCell>
                <TableCell className="px-3 py-1.5 text-sm text-center text-muted-foreground">
                  <div className="flex items-center justify-center gap-1">
                    <span>{p.opponent || "-"}</span>
                    {p.is_playing && (
                      <span className="text-[10px] text-fpl-green font-semibold tabular-nums">
                        {p.minutes}'
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="px-3 py-1.5 text-center">
                  <StatusBadge status={p.status || "a"} chanceOfPlaying={p.chance_of_playing} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export default function OpponentTeamPage() {
  const { leagueId, entryId } = useParams<{ leagueId: string; entryId: string }>();
  const navigate = useNavigate();

  const refetchInterval = useAutoRefreshInterval();
  const entryQuery = useQuery({
    queryKey: ["leagueEntry", leagueId, entryId],
    queryFn: () => api.getLeagueEntry(Number(leagueId), Number(entryId)),
    enabled: !!leagueId && !!entryId,
    refetchInterval,
    refetchIntervalInBackground: true,
  });
  const { data, isLoading, isError } = entryQuery;
  const lastUpdated = entryQuery.dataUpdatedAt
    ? new Date(entryQuery.dataUpdatedAt).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : null;

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div>
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="mb-4 -ml-2">
          <ArrowLeft className="h-4 w-4 mr-1" /> Back
        </Button>
        <p className="text-fpl-pink">Failed to load team data.</p>
      </div>
    );
  }

  const d = data as any;
  const starters = d.players?.filter((p: any) => p.is_starter) ?? [];
  const bench = d.players?.filter((p: any) => !p.is_starter) ?? [];
  const xiTotal = starters.reduce((s: number, p: any) => s + (p.gw_points || 0), 0);
  const transfers: any[] = d.transfers ?? [];

  // Group transfers by gameweek, show last 3 GWs
  const transfersByGw: Record<number, any[]> = {};
  for (const t of transfers) {
    if (!transfersByGw[t.event]) transfersByGw[t.event] = [];
    transfersByGw[t.event].push(t);
  }
  const recentGws = Object.keys(transfersByGw)
    .map(Number)
    .sort((a, b) => b - a)
    .slice(0, 3);

  return (
    <div>
      <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="mb-4 -ml-2">
        <ArrowLeft className="h-4 w-4 mr-1" /> Back to Standings
      </Button>

      <PageHeader
        title={d.team_name || "Opponent Team"}
        subtitle={d.manager_name}
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
          </div>
        }
      />

      {/* Info badges */}
      <div className="flex flex-wrap gap-2 mb-4">
        <Badge className="bg-fpl-green/15 text-fpl-green border border-fpl-green/30">GW{d.gameweek}</Badge>
        <Badge className="bg-fpl-green/15 text-fpl-green border border-fpl-green/30">GW Pts: {d.gameweek_points ?? 0}</Badge>
        <Badge className="bg-fpl-green/15 text-fpl-green border border-fpl-green/30">XI Live: {xiTotal}</Badge>
        <Badge variant="outline">{d.overall_points?.toLocaleString()} pts</Badge>
        <Badge variant="outline">Rank: {d.overall_rank?.toLocaleString()}</Badge>
        <Badge variant="outline">Bank: {'\u00A3'}{(d.bank || 0).toFixed(1)}m</Badge>
        <Badge variant="outline">Value: {'\u00A3'}{(d.squad_value || 0).toFixed(1)}m</Badge>
        <Badge variant="outline">FT: {d.free_transfers}</Badge>
        {d.transfers_made > 0 && (
          <Badge className="bg-fpl-pink/15 text-fpl-pink border border-fpl-pink/30">
            {d.transfers_made} transfer{d.transfers_made > 1 ? "s" : ""} made
          </Badge>
        )}
        {d.active_chip && (
          <Badge className="bg-fpl-gold/15 text-fpl-gold border border-fpl-gold/30">
            <Zap className="h-3 w-3 mr-1" />
            {CHIP_LABELS[d.active_chip] || d.active_chip} Active
          </Badge>
        )}
      </div>

      {starters.length > 0 && <PlayerTable players={starters} title="Starting XI" />}
      {bench.length > 0 && <PlayerTable players={bench} title="Bench" dimmed />}

      {/* Chips Used */}
      {d.chips && d.chips.length > 0 && (
        <Card className="card-stripe mt-4">
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">
              Chips Used
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="flex flex-wrap gap-2">
              {d.chips.map((c: any, i: number) => (
                <Badge key={i} variant="outline" className="text-xs">
                  <Zap className="h-3 w-3 mr-1 text-fpl-gold" />
                  {CHIP_LABELS[c.name] || c.name} — GW{c.event}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Transfers */}
      {recentGws.length > 0 && (
        <Card className="card-stripe mt-4">
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">
              Recent Transfers
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            {recentGws.map((gw) => (
              <div key={gw} className="mb-4 last:mb-0">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  Gameweek {gw}
                </p>
                {transfersByGw[gw].map((t: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 py-1.5 border-b border-border/20 last:border-0">
                    <span className="text-sm font-semibold text-fpl-pink">{t.element_out_name}</span>
                    <span className="text-[10px] text-muted-foreground">{'\u00A3'}{(t.element_out_cost / 10).toFixed(1)}m</span>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-sm font-semibold text-fpl-green">{t.element_in_name}</span>
                    <span className="text-[10px] text-muted-foreground">{'\u00A3'}{(t.element_in_cost / 10).toFixed(1)}m</span>
                  </div>
                ))}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
