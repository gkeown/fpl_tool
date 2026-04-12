import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAutoRefreshInterval } from "@/hooks/use-auto-refresh";
import PageHeader from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Loader2, Plus, Trash2, RotateCw, Trophy } from "lucide-react";

export default function LeaguePage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [leagueId, setLeagueId] = useState("");
  const [selectedLeague, setSelectedLeague] = useState<number | null>(null);

  const leagues = useQuery({
    queryKey: ["leagues"],
    queryFn: () => api.getLeagues(),
  });

  const addLeague = useMutation({
    mutationFn: () => api.addLeague(Number(leagueId)),
    onSuccess: (data: any) => {
      qc.invalidateQueries({ queryKey: ["leagues"] });
      setLeagueId("");
      setSelectedLeague(data.league_id);
    },
  });

  const removeLeague = useMutation({
    mutationFn: (id: number) => api.removeLeague(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leagues"] });
      setSelectedLeague(null);
    },
  });

  const refetchInterval = useAutoRefreshInterval();
  const leagueList = (leagues.data as any[]) ?? [];

  // Auto-select first league if none selected
  const activeLeagueId = selectedLeague ?? leagueList[0]?.league_id ?? null;

  const standings = useQuery({
    queryKey: ["leagueStandings", activeLeagueId],
    queryFn: () => api.getLeagueStandings(activeLeagueId!),
    enabled: activeLeagueId != null,
    refetchInterval,
    refetchIntervalInBackground: true,
  });

  const standingsData = standings.data as any;
  const rows = standingsData?.standings ?? [];

  return (
    <div>
      <PageHeader title="Leagues" />

      {/* Add League */}
      <Card className="card-stripe mb-6">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">
            Subscribe to a League
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-3">
            Enter a classic league ID from FPL. Find it in the URL at fantasy.premierleague.com/leagues/<strong className="text-foreground">123456</strong>/standings/c.
          </p>
          <div className="flex items-center gap-3 flex-wrap">
            <Input
              type="number"
              placeholder="e.g. 620795"
              value={leagueId}
              onChange={(e) => setLeagueId(e.target.value)}
              className="w-48"
            />
            <Button
              onClick={() => addLeague.mutate()}
              disabled={!leagueId || addLeague.isPending}
              className="bg-fpl-green text-black hover:bg-fpl-green/80 font-semibold"
            >
              {addLeague.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Plus className="h-4 w-4 mr-1" />}
              Add League
            </Button>
          </div>
          {addLeague.isError && (
            <Alert variant="destructive" className="mt-3">
              <AlertDescription>Failed to add league. Check the ID and try again.</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* League Tabs */}
      {leagueList.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-4">
          {leagueList.map((lg: any) => (
            <Button
              key={lg.league_id}
              variant={activeLeagueId === lg.league_id ? "default" : "outline"}
              size="sm"
              onClick={() => setSelectedLeague(lg.league_id)}
              className={activeLeagueId === lg.league_id ? "bg-fpl-green text-black hover:bg-fpl-green/80" : ""}
            >
              <Trophy className="h-3.5 w-3.5 mr-1" />
              {lg.name}
            </Button>
          ))}
        </div>
      )}

      {/* Standings */}
      {activeLeagueId && (
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-xs font-sans font-semibold uppercase tracking-widest text-muted-foreground">
              {standingsData?.name || "Standings"}
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => qc.invalidateQueries({ queryKey: ["leagueStandings", activeLeagueId] })}
              >
                <RotateCw className="h-3.5 w-3.5 mr-1" />
                Refresh
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeLeague.mutate(activeLeagueId)}
                className="text-fpl-pink hover:text-fpl-pink"
              >
                <Trash2 className="h-3.5 w-3.5 mr-1" />
                Remove
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {standings.isLoading ? (
              <div className="p-4 space-y-2">
                {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/20 hover:bg-muted/20">
                      <TableHead className="h-9 px-3 text-xs w-16">#</TableHead>
                      <TableHead className="h-9 px-3 text-xs">Manager</TableHead>
                      <TableHead className="h-9 px-3 text-xs">Team</TableHead>
                      <TableHead className="h-9 px-3 text-xs text-right">GW Pts</TableHead>
                      <TableHead className="h-9 px-3 text-xs text-right">Total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((r: any) => (
                      <TableRow
                        key={r.entry_id}
                        className="border-b border-border/20 cursor-pointer hover:bg-fpl-green/5 transition-colors"
                        onClick={() => navigate(`/leagues/${activeLeagueId}/team/${r.entry_id}`)}
                      >
                        <TableCell className="px-3 py-2 text-sm font-bold text-muted-foreground tabular-nums">{r.rank}</TableCell>
                        <TableCell className="px-3 py-2 text-sm font-medium">{r.player_name}</TableCell>
                        <TableCell className="px-3 py-2 text-sm text-muted-foreground">{r.entry_name}</TableCell>
                        <TableCell className="px-3 py-2 text-sm text-right tabular-nums font-semibold">{r.event_total}</TableCell>
                        <TableCell className="px-3 py-2 text-sm text-right tabular-nums">{r.total?.toLocaleString()}</TableCell>
                      </TableRow>
                    ))}
                    {rows.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                          No standings data
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {leagueList.length === 0 && !leagues.isLoading && (
        <div className="text-center py-12 text-muted-foreground">
          <Trophy className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p className="text-lg font-display">No leagues subscribed</p>
          <p className="text-sm mt-1">Add a league above to track your rivals</p>
        </div>
      )}
    </div>
  );
}
