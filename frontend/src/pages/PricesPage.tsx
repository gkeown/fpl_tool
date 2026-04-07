import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Box, Typography, Tabs, Tab, Chip } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { api } from '@/lib/api';

// /api/prices/risers and /api/prices/fallers response shape:
// rank, id, player, team, position, cost, ownership,
// transfers_in_event, transfers_out_event, net_transfers_event, pressure

const makeColumns = (isRisers: boolean): GridColDef[] => [
  { field: 'rank', headerName: '#', width: 60, type: 'number' },
  { field: 'player', headerName: 'Player', flex: 1, minWidth: 130 },
  { field: 'team', headerName: 'Team', width: 80 },
  { field: 'position', headerName: 'Pos', width: 70 },
  {
    field: 'cost', headerName: 'Price', width: 90,
    valueFormatter: (v: any) => v != null ? `£${parseFloat(v)}m` : '-',
  },
  {
    field: 'ownership', headerName: 'Own%', width: 85, type: 'number',
    valueFormatter: (v: number) => v != null ? `${v.toFixed(1)}%` : '-',
  },
  {
    field: 'transfers_in_event', headerName: 'Transfers In', width: 120, type: 'number',
    valueFormatter: (v: number) => v != null ? v.toLocaleString() : '-',
  },
  {
    field: 'transfers_out_event', headerName: 'Transfers Out', width: 125, type: 'number',
    valueFormatter: (v: number) => v != null ? v.toLocaleString() : '-',
  },
  {
    field: 'net_transfers_event', headerName: 'Net Transfers', width: 130, type: 'number',
    renderCell: (p) => {
      const val = p.value as number;
      const color = val > 0 ? '#00ff87' : '#e90052';
      return (
        <Typography sx={{ color, fontWeight: 600 }}>
          {val > 0 ? '+' : ''}{(val || 0).toLocaleString()}
        </Typography>
      );
    },
  },
  {
    field: 'pressure', headerName: 'Pressure', width: 130,
    renderCell: (p) => {
      const val = Math.abs(p.value as number ?? 0);
      const color = isRisers ? '#00ff87' : '#e90052';
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
          <Box sx={{ flex: 1, height: 8, borderRadius: 4, bgcolor: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
            <Box
              sx={{
                width: `${Math.min(val, 100)}%`,
                height: '100%',
                borderRadius: 4,
                bgcolor: color,
              }}
            />
          </Box>
          <Typography variant="caption" sx={{ color, minWidth: 35, textAlign: 'right' }}>
            {(p.value as number ?? 0).toFixed(1)}
          </Typography>
        </Box>
      );
    },
  },
];

export default function PricesPage() {
  const [tab, setTab] = useState(0);

  const risers = useQuery({
    queryKey: ['risers'],
    queryFn: () => api.getPriceRisers(20),
    enabled: tab === 0,
  });
  const fallers = useQuery({
    queryKey: ['fallers'],
    queryFn: () => api.getPriceFallers(20),
    enabled: tab === 1,
  });

  const isRisers = tab === 0;
  const activeQuery = isRisers ? risers : fallers;
  const rows = (activeQuery.data as any[]) ?? [];
  const columns = makeColumns(isRisers);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>Price Changes</Typography>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label="Risers" />
        <Tab label="Fallers" />
      </Tabs>

      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        <Chip
          label={isRisers ? 'Price rising — high transfer activity' : 'Price falling — high outflow'}
          size="small"
          color={isRisers ? 'success' : 'error'}
          variant="outlined"
        />
      </Box>

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(r) => r.id}
        autoHeight
        pageSizeOptions={[20, 50]}
        initialState={{ pagination: { paginationModel: { pageSize: 20 } } }}
        disableRowSelectionOnClick
        loading={activeQuery.isLoading}
      />
    </Box>
  );
}
