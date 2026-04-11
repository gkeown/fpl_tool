import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import FormBadge from "@/components/FormBadge";
import FDRBadge from "@/components/FDRBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowRight } from "lucide-react";

export default function TransfersPage() {
  const suggestions = useQuery({
    queryKey: ["transfers"],
    queryFn: () => api.getTransferSuggestions({ top: "10" }),
  });

  const rows = (suggestions.data as any[]) ?? [];

  if (suggestions.isLoading) {
    return (
      <div>
        <PageHeader title="Transfer Suggestions" />
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Transfer Suggestions" subtitle="Recommended transfers based on form, fixture difficulty, and value." />

      {suggestions.isError && (
        <Alert className="mb-4 border-fpl-gold/30 bg-fpl-gold/5">
          <AlertDescription>Transfer suggestions unavailable. Ensure you have loaded your team in Settings.</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/20 hover:bg-muted/20">
                  <TableHead className="h-9 px-3 text-xs w-12">#</TableHead>
                  <TableHead className="h-9 px-3 text-xs">Out</TableHead>
                  <TableHead className="h-9 px-3 text-xs w-8"></TableHead>
                  <TableHead className="h-9 px-3 text-xs">In</TableHead>
                  <TableHead className="h-9 px-3 text-xs text-center">Pos</TableHead>
                  <TableHead className="h-9 px-3 text-xs text-right">Cost Out</TableHead>
                  <TableHead className="h-9 px-3 text-xs text-right">Cost In</TableHead>
                  <TableHead className="h-9 px-3 text-xs text-right">Budget</TableHead>
                  <TableHead className="h-9 px-3 text-xs text-center">Form Out</TableHead>
                  <TableHead className="h-9 px-3 text-xs text-center">Form In</TableHead>
                  <TableHead className="h-9 px-3 text-xs text-center">FDR Out</TableHead>
                  <TableHead className="h-9 px-3 text-xs text-center">FDR In</TableHead>
                  <TableHead className="h-9 px-3 text-xs text-right">Delta</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r: any) => (
                  <TableRow key={r.rank} className="border-b border-border/20">
                    <TableCell className="px-3 py-2 text-sm text-muted-foreground font-bold tabular-nums">{r.rank}</TableCell>
                    <TableCell className="px-3 py-2">
                      <span className="font-semibold text-sm text-fpl-pink">{r.out_player}</span>
                      <span className="block text-[10px] text-muted-foreground">{r.out_team}</span>
                    </TableCell>
                    <TableCell className="px-1 py-2">
                      <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                    </TableCell>
                    <TableCell className="px-3 py-2">
                      <span className="font-semibold text-sm text-fpl-green">{r.in_player}</span>
                      <span className="block text-[10px] text-muted-foreground">{r.in_team}</span>
                    </TableCell>
                    <TableCell className="px-3 py-2 text-center">
                      <Badge variant="outline" className="text-[10px]">{r.position}</Badge>
                    </TableCell>
                    <TableCell className="px-3 py-2 text-right text-sm tabular-nums">{'\u00A3'}{parseFloat(r.out_cost) || 0}m</TableCell>
                    <TableCell className="px-3 py-2 text-right text-sm tabular-nums">{'\u00A3'}{parseFloat(r.in_cost) || 0}m</TableCell>
                    <TableCell className="px-3 py-2 text-right">
                      <span className={`font-semibold text-sm tabular-nums ${(r.budget_impact || 0) >= 0 ? "text-fpl-green" : "text-fpl-pink"}`}>
                        {(r.budget_impact || 0) >= 0 ? "+" : ""}{r.budget_impact}
                      </span>
                    </TableCell>
                    <TableCell className="px-3 py-2 text-center">
                      <FormBadge value={r.out_form || 0} />
                    </TableCell>
                    <TableCell className="px-3 py-2 text-center">
                      <FormBadge value={r.in_form || 0} />
                    </TableCell>
                    <TableCell className="px-3 py-2 text-center">
                      <FDRBadge fdr={r.out_fdr || 3} />
                    </TableCell>
                    <TableCell className="px-3 py-2 text-center">
                      <FDRBadge fdr={r.in_fdr || 3} />
                    </TableCell>
                    <TableCell className="px-3 py-2 text-right">
                      <span className={`font-bold text-sm tabular-nums ${(r.delta_value || 0) > 0 ? "text-fpl-green" : "text-fpl-pink"}`}>
                        {(r.delta_value || 0) > 0 ? "+" : ""}{(r.delta_value || 0).toFixed(1)}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={13} className="py-8 text-center text-muted-foreground">
                      No transfer suggestions available
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
