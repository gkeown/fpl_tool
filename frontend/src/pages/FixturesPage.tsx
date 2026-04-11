import { useQuery } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { fdrBg, fdrTextColor } from "@/components/FDRBadge";
import { DataTable } from "@/components/DataTable";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";

function FDRHeatmap({ data }: { data: any }) {
  if (!data) return <Skeleton className="h-96 w-full" />;

  const gameweeks: number[] = data.gameweeks ?? [];
  const ratings: Record<string, Record<string, any>> = data.ratings ?? {};

  const teams: any[] = [...(data.teams ?? [])].sort((a, b) => {
    const avgFdr = (t: any) => {
      const r = ratings[String(t.id)] ?? {};
      const vals = gameweeks
        .map((gw) => r[String(gw)]?.overall)
        .filter((v: any): v is number => v != null);
      return vals.length ? vals.reduce((s: number, v: number) => s + v, 0) / vals.length : 5;
    };
    return avgFdr(a) - avgFdr(b);
  });

  if (teams.length === 0) {
    return <Alert><AlertDescription>No FDR data available.</AlertDescription></Alert>;
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/30">
              <th className="text-left px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground min-w-[80px] sticky left-0 bg-muted/30 z-10">Team</th>
              <th className="text-center px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground min-w-[55px]">Avg</th>
              {gameweeks.map((gw) => (
                <th key={gw} className="text-center px-2 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground min-w-[70px]">GW{gw}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {teams.map((team) => {
              const teamRatings = ratings[String(team.id)] ?? {};
              const vals = gameweeks
                .map((gw) => teamRatings[String(gw)]?.overall)
                .filter((v: any): v is number => v != null);
              const avg = vals.length ? vals.reduce((s: number, v: number) => s + v, 0) / vals.length : 0;

              return (
                <tr key={team.id} className="border-t border-border/20">
                  <td className="text-left px-3 py-1.5 font-semibold text-sm sticky left-0 bg-background z-10">{team.short_name}</td>
                  <td
                    className="text-center px-2 py-1.5 text-xs font-bold"
                    style={avg > 0 ? { backgroundColor: fdrBg(avg), color: fdrTextColor(avg) } : {}}
                  >
                    {avg > 0 ? avg.toFixed(1) : "\u2014"}
                  </td>
                  {gameweeks.map((gw) => {
                    const entry = teamRatings[String(gw)];
                    if (!entry) {
                      return <td key={gw} className="text-center px-2 py-1.5 text-xs text-muted-foreground/40">{"\u2014"}</td>;
                    }
                    const fdr = entry.overall ?? 3;
                    return (
                      <td
                        key={gw}
                        className="text-center px-2 py-1.5 text-[11px] font-bold"
                        style={{ backgroundColor: fdrBg(fdr), color: fdrTextColor(fdr) }}
                      >
                        {entry.is_home ? "" : "@"}{entry.opponent}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap gap-2 mt-3">
        {[
          { label: "1-2 Easy", bg: "#00ff87", color: "#000" },
          { label: "2-2.5", bg: "#5ec960", color: "#000" },
          { label: "2.5-3", bg: "#97b84e", color: "#000" },
          { label: "3-3.5", bg: "#d4a43a", color: "#000" },
          { label: "3.5-4", bg: "#f58a23", color: "#fff" },
          { label: "4+ Hard", bg: "#e90052", color: "#fff" },
        ].map((l) => (
          <span
            key={l.label}
            className="inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-bold"
            style={{ backgroundColor: l.bg, color: l.color }}
          >
            {l.label}
          </span>
        ))}
      </div>
    </div>
  );
}

const predColumns: ColumnDef<any, any>[] = [
  { accessorKey: "gameweek", header: "GW", size: 50 },
  { accessorKey: "home_team", header: "Home" },
  { accessorKey: "away_team", header: "Away" },
  {
    accessorKey: "home_predicted_goals", header: "Home xG",
    cell: ({ row }) => <span className="tabular-nums">{row.original.home_predicted_goals?.toFixed(2) ?? "-"}</span>,
    size: 80,
  },
  {
    accessorKey: "away_predicted_goals", header: "Away xG",
    cell: ({ row }) => <span className="tabular-nums">{row.original.away_predicted_goals?.toFixed(2) ?? "-"}</span>,
    size: 80,
  },
  {
    accessorKey: "home_cs_pct", header: "Home CS%",
    cell: ({ row }) => <span className="tabular-nums">{row.original.home_cs_pct != null ? `${row.original.home_cs_pct.toFixed(0)}%` : "-"}</span>,
    size: 90,
  },
  {
    accessorKey: "away_cs_pct", header: "Away CS%",
    cell: ({ row }) => <span className="tabular-nums">{row.original.away_cs_pct != null ? `${row.original.away_cs_pct.toFixed(0)}%` : "-"}</span>,
    size: 90,
  },
  { accessorKey: "source", header: "Source", size: 100 },
];

const oddsColumns: ColumnDef<any, any>[] = [
  { accessorKey: "gameweek", header: "GW", size: 50 },
  { accessorKey: "home_team", header: "Home" },
  { accessorKey: "away_team", header: "Away" },
  {
    accessorKey: "home_win", header: "1",
    cell: ({ row }) => <span className="tabular-nums">{row.original.home_win?.toFixed(2) ?? "-"}</span>,
    size: 65,
  },
  {
    accessorKey: "draw", header: "X",
    cell: ({ row }) => <span className="tabular-nums">{row.original.draw?.toFixed(2) ?? "-"}</span>,
    size: 65,
  },
  {
    accessorKey: "away_win", header: "2",
    cell: ({ row }) => <span className="tabular-nums">{row.original.away_win?.toFixed(2) ?? "-"}</span>,
    size: 65,
  },
  {
    accessorKey: "over_2_5", header: "O2.5",
    cell: ({ row }) => <span className="tabular-nums">{row.original.over_2_5?.toFixed(2) ?? "-"}</span>,
    size: 70,
  },
  {
    accessorKey: "under_2_5", header: "U2.5",
    cell: ({ row }) => <span className="tabular-nums">{row.original.under_2_5?.toFixed(2) ?? "-"}</span>,
    size: 70,
  },
  {
    accessorKey: "btts_yes", header: "BTTS Y",
    cell: ({ row }) => <span className="tabular-nums">{row.original.btts_yes?.toFixed(2) ?? "-"}</span>,
    size: 75,
  },
  {
    accessorKey: "btts_no", header: "BTTS N",
    cell: ({ row }) => <span className="tabular-nums">{row.original.btts_no?.toFixed(2) ?? "-"}</span>,
    size: 75,
  },
];

export default function FixturesPage() {
  const fdr = useQuery({ queryKey: ["fdr"], queryFn: () => api.getFDR() });
  const predictions = useQuery({ queryKey: ["predictions"], queryFn: () => api.getPredictions() });
  const odds = useQuery({ queryKey: ["odds"], queryFn: () => api.getBettingOdds() });

  const predRows = ((predictions.data as any[]) ?? []).map((r, i) => ({ ...r, _id: r.fixture_id ?? i }));
  const oddsRows = ((odds.data as any[]) ?? []).map((r, i) => ({ ...r, _id: r.fixture_id ?? i }));

  return (
    <div>
      <PageHeader title="Fixtures" />
      <Tabs defaultValue="fdr">
        <TabsList className="bg-muted/50 mb-4">
          <TabsTrigger value="fdr" className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm">FDR Heatmap</TabsTrigger>
          <TabsTrigger value="predictions" className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm">Goal Predictions</TabsTrigger>
          <TabsTrigger value="odds" className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm">Betting Odds</TabsTrigger>
        </TabsList>

        <TabsContent value="fdr">
          {fdr.isLoading ? <Skeleton className="h-96 w-full" /> : <FDRHeatmap data={fdr.data} />}
        </TabsContent>

        <TabsContent value="predictions">
          <DataTable
            columns={predColumns}
            data={predRows}
            loading={predictions.isLoading}
            enablePagination={false}
            emptyMessage="No prediction data available"
          />
        </TabsContent>

        <TabsContent value="odds">
          <DataTable
            columns={oddsColumns}
            data={oddsRows}
            loading={odds.isLoading}
            enablePagination={false}
            emptyMessage="No betting odds available"
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
