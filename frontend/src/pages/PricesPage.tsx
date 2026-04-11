import { useQuery } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { api, PricePlayer } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

function PressureBar({ value, color }: { value: number; color: string }) {
  const width = Math.min(Math.abs(value), 100);
  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${width}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs tabular-nums min-w-[30px] text-right" style={{ color }}>
        {value.toFixed(1)}
      </span>
    </div>
  );
}

function makeColumns(isRisers: boolean): ColumnDef<PricePlayer, any>[] {
  const accentColor = isRisers ? "#00ff87" : "#e90052";
  return [
    {
      accessorKey: "rank", header: "#", size: 50,
      cell: ({ row }) => <span className="text-muted-foreground tabular-nums">{row.original.rank}</span>,
      enableSorting: false,
    },
    {
      accessorKey: "player", header: "Player",
      cell: ({ row }) => <span className="font-medium">{row.original.player}</span>,
    },
    { accessorKey: "team", header: "Team", size: 70 },
    { accessorKey: "position", header: "Pos", size: 60 },
    {
      accessorKey: "cost", header: "Price", size: 80,
      cell: ({ row }) => <span className="tabular-nums">{'\u00A3'}{row.original.cost}m</span>,
    },
    {
      accessorKey: "ownership", header: "Own%", size: 75,
      cell: ({ row }) => <span className="tabular-nums">{row.original.ownership?.toFixed(1)}%</span>,
    },
    {
      accessorKey: "transfers_in_event", header: "In", size: 90,
      cell: ({ row }) => <span className="tabular-nums">{(row.original.transfers_in_event || 0).toLocaleString()}</span>,
    },
    {
      accessorKey: "transfers_out_event", header: "Out", size: 90,
      cell: ({ row }) => <span className="tabular-nums">{(row.original.transfers_out_event || 0).toLocaleString()}</span>,
    },
    {
      accessorKey: "net_transfers_event", header: "Net", size: 100,
      cell: ({ row }) => {
        const val = row.original.net_transfers_event || 0;
        return (
          <span className={`font-semibold tabular-nums ${val > 0 ? "text-fpl-green" : "text-fpl-pink"}`}>
            {val > 0 ? "+" : ""}{val.toLocaleString()}
          </span>
        );
      },
    },
    {
      accessorKey: "pressure", header: "Pressure", size: 130,
      cell: ({ row }) => <PressureBar value={Math.abs(row.original.pressure || 0)} color={accentColor} />,
    },
  ];
}

export default function PricesPage() {
  const risers = useQuery({ queryKey: ["risers"], queryFn: () => api.getPriceRisers(20) });
  const fallers = useQuery({ queryKey: ["fallers"], queryFn: () => api.getPriceFallers(20) });

  return (
    <div>
      <PageHeader title="Price Changes" />
      <Tabs defaultValue="risers">
        <TabsList className="bg-muted/50 mb-4">
          <TabsTrigger value="risers" className="data-[state=active]:bg-background data-[state=active]:text-fpl-green data-[state=active]:shadow-sm">Risers</TabsTrigger>
          <TabsTrigger value="fallers" className="data-[state=active]:bg-background data-[state=active]:text-fpl-pink data-[state=active]:shadow-sm">Fallers</TabsTrigger>
        </TabsList>

        <TabsContent value="risers">
          <Badge variant="outline" className="mb-3 bg-fpl-green/5 text-fpl-green border-fpl-green/30 text-xs">
            Price rising &mdash; high transfer activity
          </Badge>
          <DataTable
            columns={makeColumns(true)}
            data={(risers.data as PricePlayer[]) ?? []}
            loading={risers.isLoading}
            pageSize={20}
          />
        </TabsContent>

        <TabsContent value="fallers">
          <Badge variant="outline" className="mb-3 bg-fpl-pink/5 text-fpl-pink border-fpl-pink/30 text-xs">
            Price falling &mdash; high outflow
          </Badge>
          <DataTable
            columns={makeColumns(false)}
            data={(fallers.data as PricePlayer[]) ?? []}
            loading={fallers.isLoading}
            pageSize={20}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
