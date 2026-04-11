import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import FormBadge from "@/components/FormBadge";
import StatusBadge from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { RotateCw, AlertTriangle, Zap } from "lucide-react";

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
              <TableHead className="h-8 px-3 text-xs text-right">xPts GW</TableHead>
              <TableHead className="h-8 px-3 text-xs text-center">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {players.map((p: any) => (
              <TableRow key={p.id} className={`border-b border-border/20 ${p.is_captain ? "bg-fpl-green/5" : ""}`}>
                <TableCell className="px-3 py-1.5 text-sm">{p.position}</TableCell>
                <TableCell className="px-3 py-1.5 text-sm">
                  <div className="flex items-center gap-1.5">
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
                <TableCell className="px-3 py-1.5 text-sm text-right">{'\u00A3'}{(p.cost || p.selling_price || 0).toFixed(1)}m</TableCell>
                <TableCell className="px-3 py-1.5 text-right">
                  <FormBadge value={p.form || 0} />
                </TableCell>
                <TableCell className="px-3 py-1.5 text-sm text-right tabular-nums">
                  <span className={`font-semibold ${(p.gw_points || 0) >= 8 ? "text-fpl-green" : ""}`}>
                    {p.gw_points ?? 0}
                  </span>
                </TableCell>
                <TableCell className="px-3 py-1.5 text-sm text-right tabular-nums">
                  <span className={(p.gw_bonus || 0) >= 3 ? "text-fpl-gold font-semibold" : ""}>
                    {p.gw_bonus ?? 0}
                  </span>
                </TableCell>
                <TableCell className="px-3 py-1.5 text-sm text-right tabular-nums">{(p.xpts_next_gw || 0).toFixed(1)}</TableCell>
                <TableCell className="px-3 py-1.5 text-center">
                  <StatusBadge status={p.status || "a"} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export default function MyTeamPage() {
  const qc = useQueryClient();
  const team = useQuery({ queryKey: ["team"], queryFn: () => api.getTeam() });
  const analysis = useQuery({ queryKey: ["teamAnalysis"], queryFn: () => api.getTeamAnalysis(5) });

  const teamData = team.data as any;
  const analysisData = analysis.data as any;

  const starters = teamData?.players?.filter((p: any) => p.is_starter) ?? [];
  const bench = teamData?.players?.filter((p: any) => !p.is_starter) ?? [];
  const xiTotal = starters.reduce((s: number, p: any) => s + (p.gw_points || 0), 0);

  if (team.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="My Team"
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              qc.invalidateQueries({ queryKey: ["team"] });
              qc.invalidateQueries({ queryKey: ["teamAnalysis"] });
            }}
          >
            <RotateCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        }
      />

      {team.isError && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>Failed to load team data. Go to Settings and enter your FPL Team ID first.</AlertDescription>
        </Alert>
      )}

      {teamData && (
        <div className="flex flex-wrap gap-2 mb-4">
          <Badge className="bg-fpl-green/15 text-fpl-green border border-fpl-green/30">GW{teamData.gameweek}</Badge>
          <Badge className="bg-fpl-green/15 text-fpl-green border border-fpl-green/30">GW Pts: {teamData.gameweek_points ?? 0}</Badge>
          <Badge className="bg-fpl-green/15 text-fpl-green border border-fpl-green/30">XI Live: {xiTotal}</Badge>
          <Badge variant="outline">{teamData.overall_points?.toLocaleString()} pts</Badge>
          <Badge variant="outline">Rank: {teamData.overall_rank?.toLocaleString()}</Badge>
          <Badge variant="outline">Bank: {'\u00A3'}{(teamData.bank || 0).toFixed(1)}m</Badge>
          <Badge variant="outline">Free Transfers: {teamData.free_transfers}</Badge>
          {teamData.active_chip && (
            <Badge className="bg-fpl-gold/15 text-fpl-gold border border-fpl-gold/30">
              <Zap className="h-3 w-3 mr-1" />
              {CHIP_LABELS[teamData.active_chip] || teamData.active_chip} Active
            </Badge>
          )}
        </div>
      )}

      {analysisData && (
        <div className="flex flex-wrap gap-2 mb-4">
          <Badge className="bg-fpl-green/15 text-fpl-green border border-fpl-green/30 animate-pulse-glow">
            Next GW xPts: {(analysisData.projected_xi_gw1 || 0).toFixed(1)}
          </Badge>
          <Badge variant="outline">3 GW xPts: {(analysisData.projected_xi_3gw || 0).toFixed(1)}</Badge>
          <Badge variant="outline">5 GW xPts: {(analysisData.projected_xi_5gw || 0).toFixed(1)}</Badge>
          <Badge variant="outline">Squad Strength: {(analysisData.squad_strength || 0).toFixed(1)}</Badge>
        </div>
      )}

      {starters.length > 0 && <PlayerTable players={starters} title="Starting XI" />}
      {bench.length > 0 && <PlayerTable players={bench} title="Bench" dimmed />}

      {analysisData?.weak_spots && analysisData.weak_spots.length > 0 && (
        <div className="mt-4 space-y-2">
          <h3 className="text-sm font-sans font-semibold uppercase tracking-widest text-muted-foreground">Weak Spots</h3>
          {analysisData.weak_spots.map((w: string, i: number) => (
            <Alert key={i} className="border-fpl-gold/30 bg-fpl-gold/5">
              <AlertTriangle className="h-4 w-4 text-fpl-gold" />
              <AlertDescription className="text-sm">{w}</AlertDescription>
            </Alert>
          ))}
        </div>
      )}

      {teamData?.chips && teamData.chips.length > 0 && (
        <Card className="card-stripe mt-4">
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">
              Chips Used
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="flex flex-wrap gap-2">
              {teamData.chips.map((c: any, i: number) => (
                <Badge key={i} variant="outline" className="text-xs">
                  <Zap className="h-3 w-3 mr-1 text-fpl-gold" />
                  {CHIP_LABELS[c.name] || c.name} — GW{c.event}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
