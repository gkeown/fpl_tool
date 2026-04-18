import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import StatCard from "@/components/StatCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import PageHeader from "@/components/PageHeader";
import { Crown, Newspaper, RotateCw, Loader2, CheckCircle } from "lucide-react";

export default function DashboardPage() {
  const qc = useQueryClient();
  const team = useQuery({ queryKey: ["team"], queryFn: () => api.getTeam() });
  const captains = useQuery({ queryKey: ["captains"], queryFn: () => api.getCaptains() });
  const predictions = useQuery({ queryKey: ["predictions"], queryFn: () => api.getPredictions() });
  const news = useQuery({ queryKey: ["news"], queryFn: () => api.getNews() });

  const refresh = useMutation({
    mutationFn: () => api.refreshAll("all", true),
    onSuccess: () => {
      qc.invalidateQueries();
    },
  });

  const teamData = team.data as any;
  const starters = teamData?.players?.filter((p: any) => p.is_starter) || [];
  const xiTotal = starters.reduce((s: number, p: any) => s + (p.gw_points || 0) + (p.gw_bonus || 0), 0);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        actions={
          <div className="flex items-center gap-2">
            {refresh.isSuccess && (
              <span className="flex items-center gap-1 text-xs text-fpl-green">
                <CheckCircle className="h-3.5 w-3.5" />
                Updated
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => refresh.mutate()}
              disabled={refresh.isPending}
            >
              {refresh.isPending ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <RotateCw className="h-4 w-4 mr-1" />
              )}
              {refresh.isPending ? "Refreshing..." : "Refresh Data"}
            </Button>
          </div>
        }
      />

      {refresh.isError && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>Data refresh failed. Check the server logs.</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Team Summary */}
        <StatCard title="Team Summary" loading={team.isLoading}>
          {teamData ? (
            <div>
              <div className="flex items-baseline gap-6 mb-3">
                <div>
                  <span className="text-4xl font-display font-bold text-fpl-green">{xiTotal}</span>
                  <p className="text-xs text-muted-foreground mt-0.5">GW{teamData.gameweek} XI Live</p>
                </div>
                <div>
                  <span className="text-2xl font-display font-semibold text-muted-foreground">{teamData.overall_points}</span>
                  <p className="text-xs text-muted-foreground mt-0.5">Total Points</p>
                </div>
                <div>
                  <span className="text-2xl font-display font-semibold text-muted-foreground">{teamData.overall_rank?.toLocaleString()}</span>
                  <p className="text-xs text-muted-foreground mt-0.5">Overall Rank</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className="text-xs">Bank: {'\u00A3'}{(teamData.bank || 0).toFixed(1)}m</Badge>
                <Badge variant="outline" className="text-xs">FT: {teamData.free_transfers}</Badge>
                <Badge className="text-xs bg-fpl-green/15 text-fpl-green border border-fpl-green/30">GW{teamData.gameweek}</Badge>
              </div>
            </div>
          ) : team.isError ? (
            <Alert variant="destructive"><AlertDescription>Failed to load team data. Run 'fpl me login' first.</AlertDescription></Alert>
          ) : null}
        </StatCard>

        {/* Captain Picks */}
        <StatCard title="Captain Picks" icon={<Crown className="h-3.5 w-3.5" />} loading={captains.isLoading}>
          {(captains.data as any[])?.slice(0, 3).map((c: any, i: number) => (
            <div
              key={i}
              className={`flex items-center justify-between py-2.5 ${i < 2 ? "border-b border-border/40" : ""} ${i === 0 ? "pl-2 border-l-2 border-l-fpl-green" : ""}`}
            >
              <div className={i === 0 ? "ml-2" : ""}>
                <p className="font-semibold text-sm">{c.player}</p>
                <p className="text-xs text-muted-foreground">{c.team} &middot; {c.fixture}</p>
              </div>
              <Badge className={i === 0 ? "bg-fpl-green/15 text-fpl-green border border-fpl-green/30" : "bg-muted text-muted-foreground"}>
                {(c.captain_score || 0).toFixed(1)}
              </Badge>
            </div>
          ))}
          {captains.isError && <p className="text-sm text-muted-foreground">No captain data available</p>}
        </StatCard>

        {/* Predictions */}
        <StatCard title="Match Predictions" loading={predictions.isLoading}>
          {(predictions.data as any[])?.slice(0, 6).map((f: any, i: number) => (
            <div key={i} className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
              <span className="text-sm">{f.home_team} vs {f.away_team}</span>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-xs tabular-nums">
                  {(f.home_predicted_goals || 0).toFixed(1)} - {(f.away_predicted_goals || 0).toFixed(1)}
                </Badge>
                <span className="text-[10px] text-muted-foreground tabular-nums">
                  CS: {f.home_cs_pct?.toFixed(0)}%/{f.away_cs_pct?.toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
        </StatCard>

        {/* News */}
        <StatCard title="Latest News" icon={<Newspaper className="h-3.5 w-3.5" />} loading={news.isLoading}>
          {(news.data as any[])?.slice(0, 5).map((n: any, i: number) => (
            <div key={i} className="py-1.5 border-b border-border/30 last:border-0">
              <a
                href={n.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium hover:text-fpl-green transition-colors"
              >
                {n.title}
              </a>
              <p className="text-[10px] text-muted-foreground mt-0.5">{n.published}</p>
            </div>
          ))}
        </StatCard>
      </div>
    </div>
  );
}
