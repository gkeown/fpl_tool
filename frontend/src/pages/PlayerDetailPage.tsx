import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import FormBadge from "@/components/FormBadge";
import StatusBadge from "@/components/StatusBadge";
import FDRBadge, { fdrBg, fdrTextColor } from "@/components/FDRBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, AlertTriangle } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

function StatGrid({ data }: { data: Record<string, any> }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {Object.entries(data).map(([key, val]) => (
        <div key={key} className="p-2 rounded-md bg-muted/30">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider capitalize">
            {key.replace(/_/g, " ")}
          </p>
          <p className="text-sm font-semibold mt-0.5">{val != null ? String(val) : "-"}</p>
        </div>
      ))}
    </div>
  );
}

export default function PlayerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: player, isLoading, isError } = useQuery({
    queryKey: ["player", id],
    queryFn: () => api.getPlayer(Number(id)),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }
  if (isError) return <Alert variant="destructive"><AlertDescription>Failed to load player data.</AlertDescription></Alert>;
  if (!player) return <p className="text-muted-foreground">Player not found</p>;

  const p = player as any;
  const recentHistory: any[] = p.recent_history ?? [];
  const projections: any = p.projections ?? {};
  const upcomingFixtures: any[] = p.upcoming_fixtures ?? [];
  const setPieceNotes: string[] = p.set_piece_notes ?? [];
  const seasonStats: any = p.season_stats ?? {};
  const defensiveStats: any = p.defensive_stats;
  const chartData = recentHistory.slice(-10);

  const projRows = [
    { label: "Next GW", value: projections.gw1_pts },
    { label: "Next 2 GW", value: projections.gw2_pts },
    { label: "Next 3 GW", value: projections.gw3_pts },
    { label: "Next 4 GW", value: projections.gw4_pts },
    { label: "Next 5 GW", value: projections.gw5_pts },
    { label: "3 GW Total", value: projections.next_3gw_pts },
    { label: "5 GW Total", value: projections.next_5gw_pts },
  ].filter((r) => r.value != null);

  return (
    <div>
      <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="mb-4 -ml-2">
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back
      </Button>

      {/* Player Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-display font-bold">{p.web_name || p.name}</h1>
        {p.name && p.web_name && p.name !== p.web_name && (
          <p className="text-sm text-muted-foreground">{p.name}</p>
        )}
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge variant="outline">{p.team_short || p.team}</Badge>
          <Badge className="bg-muted text-foreground">{p.position}</Badge>
          <Badge variant="outline">{'\u00A3'}{parseFloat(p.cost) || 0}m</Badge>
          <FormBadge value={parseFloat(p.form) || 0} />
          <StatusBadge status={p.status || "a"} chanceOfPlaying={p.chance_of_playing} />
        </div>
        {p.news && (
          <Alert className="mt-3 border-fpl-gold/30 bg-fpl-gold/5">
            <AlertTriangle className="h-4 w-4 text-fpl-gold" />
            <AlertDescription className="text-sm">{p.news}</AlertDescription>
          </Alert>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Season Stats */}
        {Object.keys(seasonStats).length > 0 && (
          <Card className="card-stripe">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">Season Stats</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <StatGrid data={seasonStats} />
            </CardContent>
          </Card>
        )}

        {/* Defensive Stats */}
        {defensiveStats && Object.keys(defensiveStats).length > 0 && (
          <Card className="card-stripe">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">Defensive Stats</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <StatGrid data={defensiveStats} />
            </CardContent>
          </Card>
        )}

        {/* Points Chart */}
        {chartData.length > 0 && (
          <Card className="card-stripe">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">
                Recent Form (Last {chartData.length} GWs)
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(222 20% 18%)" />
                  <XAxis
                    dataKey="gameweek"
                    stroke="hsl(215 18% 47%)"
                    tick={{ fontSize: 11, fill: "hsl(215 18% 47%)" }}
                    label={{ value: "GW", position: "insideRight", offset: -5, fill: "hsl(215 18% 47%)", fontSize: 10 }}
                  />
                  <YAxis stroke="hsl(215 18% 47%)" tick={{ fontSize: 11, fill: "hsl(215 18% 47%)" }} />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(222 40% 10%)",
                      border: "1px solid hsl(222 20% 18%)",
                      borderRadius: "8px",
                      fontSize: 12,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="total_points"
                    stroke="#00ff87"
                    strokeWidth={2}
                    dot={{ fill: "#00ff87", r: 3 }}
                    name="Points"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Projections */}
        {projRows.length > 0 && (
          <Card className="card-stripe">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">Projected Points</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="h-8 px-2 text-xs">Period</TableHead>
                    <TableHead className="h-8 px-2 text-xs text-right">xPts</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {projRows.map((r) => (
                    <TableRow key={r.label} className="border-b border-border/20">
                      <TableCell className="px-2 py-1.5 text-sm">{r.label}</TableCell>
                      <TableCell className="px-2 py-1.5 text-right">
                        <span className="font-bold text-fpl-green tabular-nums">{Number(r.value).toFixed(1)}</span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

        {/* Upcoming Fixtures */}
        {upcomingFixtures.length > 0 && (
          <Card className="card-stripe">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">Upcoming Fixtures</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <div className="flex flex-wrap gap-2">
                {upcomingFixtures.map((f: any, i: number) => {
                  const fdr = f.difficulty || f.fdr || f.overall_difficulty || 3;
                  return (
                    <div
                      key={i}
                      className="rounded-md px-3 py-1.5 text-xs font-bold"
                      style={{ backgroundColor: fdrBg(fdr), color: fdrTextColor(fdr) }}
                    >
                      GW{f.gameweek || f.gw}: {f.is_home ? "" : "@"}{f.team_short || f.opponent || f.team}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Set-Piece Notes */}
        {setPieceNotes.length > 0 && (
          <Card className="card-stripe">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">Set-Piece Notes</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 space-y-2">
              {setPieceNotes.map((note, i) => (
                <div key={i} className="text-sm p-2 rounded-md bg-muted/30">{note}</div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Recent GW History - full width */}
      {recentHistory.length > 0 && (
        <Card className="card-stripe mt-4">
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">Recent GW History</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/20 hover:bg-muted/20">
                    <TableHead className="h-8 px-3 text-xs">GW</TableHead>
                    <TableHead className="h-8 px-3 text-xs">Opponent</TableHead>
                    <TableHead className="h-8 px-3 text-xs text-right">Pts</TableHead>
                    <TableHead className="h-8 px-3 text-xs text-right">Mins</TableHead>
                    <TableHead className="h-8 px-3 text-xs text-right">G</TableHead>
                    <TableHead className="h-8 px-3 text-xs text-right">A</TableHead>
                    <TableHead className="h-8 px-3 text-xs text-right">CS</TableHead>
                    <TableHead className="h-8 px-3 text-xs text-right">Saves</TableHead>
                    <TableHead className="h-8 px-3 text-xs text-right">Bonus</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentHistory.slice(-10).reverse().map((gw: any, i: number) => (
                    <TableRow key={i} className="border-b border-border/20">
                      <TableCell className="px-3 py-1.5 text-sm tabular-nums">{gw.gameweek}</TableCell>
                      <TableCell className="px-3 py-1.5 text-sm">{gw.was_home ? "H" : "A"}</TableCell>
                      <TableCell className="px-3 py-1.5 text-right">
                        <span className={`font-bold tabular-nums ${(gw.total_points || 0) >= 8 ? "text-fpl-green" : ""}`}>
                          {gw.total_points ?? "-"}
                        </span>
                      </TableCell>
                      <TableCell className="px-3 py-1.5 text-right text-sm tabular-nums">{gw.minutes ?? "-"}</TableCell>
                      <TableCell className="px-3 py-1.5 text-right text-sm tabular-nums">{gw.goals_scored ?? "-"}</TableCell>
                      <TableCell className="px-3 py-1.5 text-right text-sm tabular-nums">{gw.assists ?? "-"}</TableCell>
                      <TableCell className="px-3 py-1.5 text-right text-sm tabular-nums">{gw.clean_sheets ?? "-"}</TableCell>
                      <TableCell className="px-3 py-1.5 text-right text-sm tabular-nums">{gw.saves ?? "-"}</TableCell>
                      <TableCell className="px-3 py-1.5 text-right text-sm tabular-nums">{gw.bonus ?? "-"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
