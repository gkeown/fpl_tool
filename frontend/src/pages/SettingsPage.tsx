import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { RotateCw, Loader2, CheckCircle, XCircle } from "lucide-react";

function formatAge(secs: number): string {
  if (secs < 60) return `${Math.round(secs)}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  return `${Math.round(secs / 3600)}h ago`;
}

function formatDuration(secs: number): string {
  return secs != null ? `${secs.toFixed(1)}s` : "-";
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const [teamId, setTeamId] = useState("");

  const status = useQuery({ queryKey: ["dataStatus"], queryFn: () => api.getDataStatus() });

  const loadTeam = useMutation({
    mutationFn: () => api.loadTeam(Number(teamId)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["team"] });
      qc.invalidateQueries({ queryKey: ["teamAnalysis"] });
    },
  });

  const refreshAll = useMutation({
    mutationFn: () => api.refreshAll(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dataStatus"] });
    },
  });

  const statusRows = (status.data as any[]) ?? [];

  return (
    <div>
      <PageHeader title="Settings" />

      {/* Load Team */}
      <Card className="card-stripe mb-6">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-sans font-semibold uppercase tracking-widest text-muted-foreground">
            Load FPL Team
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-3">
            Enter your FPL team ID. Find it in the URL at fantasy.premierleague.com/entry/<strong className="text-foreground">123456</strong>/event/1.
          </p>
          <div className="flex items-center gap-3 flex-wrap">
            <Input
              type="number"
              placeholder="e.g. 123456"
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              className="w-48"
            />
            <Button
              onClick={() => loadTeam.mutate()}
              disabled={!teamId || loadTeam.isPending}
              className="bg-fpl-green text-black hover:bg-fpl-green/80 font-semibold"
            >
              {loadTeam.isPending && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
              {loadTeam.isPending ? "Loading..." : "Load Team"}
            </Button>
          </div>
          {loadTeam.isSuccess && (
            <Alert className="mt-3 border-fpl-green/30 bg-fpl-green/5">
              <CheckCircle className="h-4 w-4 text-fpl-green" />
              <AlertDescription>Team loaded successfully! Your squad data is now available.</AlertDescription>
            </Alert>
          )}
          {loadTeam.isError && (
            <Alert variant="destructive" className="mt-3">
              <XCircle className="h-4 w-4" />
              <AlertDescription>Failed to load team. Check your team ID and try again.</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Data Status */}
      <Card className="card-stripe">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-sans font-semibold uppercase tracking-widest text-muted-foreground">
            Data Status
          </CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refreshAll.mutate()}
            disabled={refreshAll.isPending}
          >
            {refreshAll.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <RotateCw className="h-4 w-4 mr-1" />}
            {refreshAll.isPending ? "Refreshing..." : "Refresh All"}
          </Button>
        </CardHeader>
        <CardContent>
          {refreshAll.isSuccess && (
            <Alert className="mb-3 border-fpl-green/30 bg-fpl-green/5">
              <CheckCircle className="h-4 w-4 text-fpl-green" />
              <AlertDescription>All data sources refreshed successfully.</AlertDescription>
            </Alert>
          )}
          {refreshAll.isError && (
            <Alert variant="destructive" className="mb-3">
              <XCircle className="h-4 w-4" />
              <AlertDescription>Refresh failed. Check the server logs.</AlertDescription>
            </Alert>
          )}

          <div className="rounded-lg border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/20 hover:bg-muted/20">
                  <TableHead className="h-8 px-3 text-xs">Source</TableHead>
                  <TableHead className="h-8 px-3 text-xs text-center">Status</TableHead>
                  <TableHead className="h-8 px-3 text-xs text-right">Records</TableHead>
                  <TableHead className="h-8 px-3 text-xs text-right">Duration</TableHead>
                  <TableHead className="h-8 px-3 text-xs text-right">Last Run</TableHead>
                  <TableHead className="h-8 px-3 text-xs">Error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {statusRows.map((row: any) => (
                  <TableRow key={row.source} className="border-b border-border/20">
                    <TableCell className="px-3 py-1.5 font-semibold text-sm">{row.source}</TableCell>
                    <TableCell className="px-3 py-1.5 text-center">
                      <Badge
                        variant="outline"
                        className={
                          row.status === "success"
                            ? "bg-fpl-green/10 text-fpl-green border-fpl-green/30 text-xs"
                            : "bg-fpl-pink/10 text-fpl-pink border-fpl-pink/30 text-xs"
                        }
                      >
                        {row.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="px-3 py-1.5 text-right text-sm tabular-nums">
                      {row.records_upserted != null ? row.records_upserted.toLocaleString() : "-"}
                    </TableCell>
                    <TableCell className="px-3 py-1.5 text-right text-sm tabular-nums">{formatDuration(row.duration_secs)}</TableCell>
                    <TableCell className="px-3 py-1.5 text-right text-sm text-muted-foreground">
                      {row.age_secs != null ? formatAge(row.age_secs) : "-"}
                    </TableCell>
                    <TableCell className="px-3 py-1.5 text-xs">
                      {row.error_message ? (
                        <span className="text-fpl-pink">{row.error_message}</span>
                      ) : (
                        <span className="text-muted-foreground/50">&mdash;</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {statusRows.length === 0 && !status.isLoading && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-6 text-center text-muted-foreground">
                      No data status available
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
