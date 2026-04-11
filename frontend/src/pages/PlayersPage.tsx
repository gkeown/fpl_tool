import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ColumnDef } from "@tanstack/react-table";
import { api, FormPlayer } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import FormBadge from "@/components/FormBadge";
import { DataTable } from "@/components/DataTable";
import { Input } from "@/components/ui/input";
import { Search, X } from "lucide-react";

const formColumns: ColumnDef<FormPlayer, any>[] = [
  {
    accessorKey: "rank",
    header: "#",
    cell: ({ row }) => <span className="text-muted-foreground tabular-nums">{row.original.rank}</span>,
    enableSorting: false,
    size: 50,
  },
  {
    accessorKey: "player",
    header: "Player",
    cell: ({ row }) => <span className="font-medium">{row.original.player}</span>,
  },
  { accessorKey: "team", header: "Team", size: 80 },
  { accessorKey: "position", header: "Pos", size: 60 },
  {
    accessorKey: "cost",
    header: "Cost",
    cell: ({ row }) => <span className="tabular-nums">{'\u00A3'}{row.original.cost}m</span>,
    size: 80,
  },
  {
    accessorKey: "form",
    header: "Form",
    cell: ({ row }) => <FormBadge value={row.original.form} />,
    size: 80,
  },
  {
    accessorKey: "xg_per90",
    header: "xG/90",
    cell: ({ row }) => <span className="tabular-nums">{row.original.xg_per90 != null ? row.original.xg_per90.toFixed(3) : "-"}</span>,
    size: 80,
  },
  {
    accessorKey: "xa_per90",
    header: "xA/90",
    cell: ({ row }) => <span className="tabular-nums">{row.original.xa_per90 != null ? row.original.xa_per90.toFixed(3) : "-"}</span>,
    size: 80,
  },
  {
    accessorKey: "pts_per90",
    header: "Pts/90",
    cell: ({ row }) => <span className="tabular-nums">{row.original.pts_per90 != null ? row.original.pts_per90.toFixed(1) : "-"}</span>,
    size: 80,
  },
];

const searchColumns: ColumnDef<any, any>[] = [
  {
    accessorKey: "player",
    header: "Player",
    cell: ({ row }) => <span className="font-medium">{row.original.player || row.original.web_name}</span>,
  },
  { accessorKey: "team", header: "Team", size: 80 },
  { accessorKey: "position", header: "Pos", size: 60 },
  {
    accessorKey: "cost",
    header: "Cost",
    cell: ({ row }) => <span className="tabular-nums">{'\u00A3'}{parseFloat(row.original.cost) || 0}m</span>,
    size: 80,
  },
  { accessorKey: "status", header: "Status", size: 70 },
  {
    accessorKey: "score",
    header: "Match%",
    cell: ({ row }) => (
      <span className="tabular-nums">
        {row.original.score != null ? `${Number(row.original.score).toFixed(0)}%` : "-"}
      </span>
    ),
    size: 80,
  },
];

export default function PlayersPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const players = useQuery({
    queryKey: ["playersForm"],
    queryFn: () => api.getPlayers({ top: "50" }),
  });

  const searchResults = useQuery({
    queryKey: ["playerSearch", searchQuery],
    queryFn: () => api.searchPlayers(searchQuery),
    enabled: searchQuery.length >= 2,
  });

  const handleSearch = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") setSearchQuery(search.trim());
  };

  const showingSearch = searchQuery.length >= 2 && searchResults.data;
  const formRows = (players.data as FormPlayer[]) ?? [];
  const searchRows = (searchResults.data as any[]) ?? [];

  return (
    <div>
      <PageHeader title="Players" subtitle="Top players by FPL form" />

      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search for any player... (press Enter)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={handleSearch}
          className="pl-10 pr-10"
        />
        {searchQuery && (
          <button
            onClick={() => { setSearch(""); setSearchQuery(""); }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {showingSearch ? (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-display font-semibold">Search: "{searchQuery}"</h2>
            <button
              onClick={() => { setSearch(""); setSearchQuery(""); }}
              className="text-sm text-fpl-green hover:underline"
            >
              Clear search
            </button>
          </div>
          <DataTable
            columns={searchColumns}
            data={searchRows}
            loading={searchResults.isLoading}
            onRowClick={(row: any) => navigate(`/players/${row.id}`)}
            enablePagination={false}
          />
        </div>
      ) : (
        <div>
          <h2 className="text-lg font-display font-semibold mb-1">Form Rankings</h2>
          <p className="text-sm text-muted-foreground mb-3">Click a row for full details.</p>
          <DataTable
            columns={formColumns}
            data={formRows}
            loading={players.isLoading}
            pageSize={20}
            onRowClick={(row: FormPlayer) => navigate(`/players/${row.id}`)}
          />
        </div>
      )}

      {players.isError && (
        <p className="text-sm text-fpl-pink mt-4">Failed to load player data.</p>
      )}
    </div>
  );
}
