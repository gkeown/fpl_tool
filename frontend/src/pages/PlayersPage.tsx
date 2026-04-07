import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Box, Typography, Chip, TextField, InputAdornment } from '@mui/material';
import { Search } from '@mui/icons-material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';

const columns: GridColDef[] = [
  { field: 'rank', headerName: '#', width: 60, type: 'number' },
  { field: 'player', headerName: 'Player', flex: 1, minWidth: 130 },
  { field: 'team', headerName: 'Team', width: 80 },
  { field: 'position', headerName: 'Pos', width: 70 },
  {
    field: 'cost', headerName: 'Cost', width: 85,
    valueFormatter: (v: any) => `£${parseFloat(v) || 0}m`,
  },
  {
    field: 'form', headerName: 'Form', width: 85,
    renderCell: (p) => {
      const val = Number(p.value);
      const color = val >= 8 ? '#00ff87' : val >= 5 ? '#f5a623' : '#e90052';
      return (
        <Chip
          label={val.toFixed(1)}
          size="small"
          sx={{ bgcolor: `${color}22`, color, fontWeight: 700, border: `1px solid ${color}` }}
        />
      );
    },
  },
  {
    field: 'xg_per90', headerName: 'xG/90', width: 90, type: 'number',
    valueFormatter: (v: any) => v != null ? Number(v).toFixed(3) : '-',
  },
  {
    field: 'xa_per90', headerName: 'xA/90', width: 90, type: 'number',
    valueFormatter: (v: any) => v != null ? Number(v).toFixed(3) : '-',
  },
  {
    field: 'pts_per90', headerName: 'Pts/90', width: 90, type: 'number',
    valueFormatter: (v: any) => v != null ? Number(v).toFixed(1) : '-',
  },
];

const searchColumns: GridColDef[] = [
  { field: 'player', headerName: 'Player', flex: 1, minWidth: 180 },
  { field: 'web_name', headerName: 'Name', width: 120 },
  { field: 'team', headerName: 'Team', width: 80 },
  { field: 'position', headerName: 'Pos', width: 70 },
  {
    field: 'cost', headerName: 'Cost', width: 85,
    valueFormatter: (v: any) => `£${parseFloat(v) || 0}m`,
  },
  { field: 'status', headerName: 'Status', width: 80 },
  {
    field: 'score', headerName: 'Match%', width: 85, type: 'number',
    valueFormatter: (v: any) => v != null ? `${Number(v).toFixed(0)}%` : '-',
  },
];

export default function PlayersPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const players = useQuery({
    queryKey: ['playersForm'],
    queryFn: () => api.getPlayers({ top: '50' }),
  });

  const searchResults = useQuery({
    queryKey: ['playerSearch', searchQuery],
    queryFn: () => api.searchPlayers(searchQuery),
    enabled: searchQuery.length >= 2,
  });

  const handleSearch = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      setSearchQuery(search.trim());
    }
  };

  const showingSearch = searchQuery.length >= 2 && searchResults.data;
  const formRows = (players.data as any[]) ?? [];
  const searchRows = (searchResults.data as any[]) ?? [];

  return (
    <Box>
      <Typography variant="h4" gutterBottom>Players</Typography>

      <TextField
        fullWidth
        placeholder="Search for any player... (press Enter)"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        onKeyDown={handleSearch}
        sx={{ mb: 3 }}
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <Search />
              </InputAdornment>
            ),
          },
        }}
      />

      {showingSearch ? (
        <>
          <Typography variant="h6" gutterBottom>
            Search results for "{searchQuery}"
          </Typography>
          <DataGrid
            rows={searchRows}
            columns={searchColumns}
            loading={searchResults.isLoading}
            getRowId={(r) => r.id}
            autoHeight
            pageSizeOptions={[20]}
            disableRowSelectionOnClick
            onRowClick={(p) => navigate(`/players/${p.id}`)}
            sx={{ cursor: 'pointer', mb: 3 }}
          />
          <Typography
            variant="body2"
            color="primary"
            sx={{ cursor: 'pointer', mb: 3 }}
            onClick={() => { setSearch(''); setSearchQuery(''); }}
          >
            Clear search — show form table
          </Typography>
        </>
      ) : (
        <>
          <Typography variant="h6" gutterBottom>
            Form Rankings
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Top players by FPL form. Click a row for full details.
          </Typography>
          <DataGrid
            rows={formRows}
            columns={columns}
            loading={players.isLoading}
            getRowId={(r) => r.id}
            autoHeight
            pageSizeOptions={[20, 50]}
            initialState={{ pagination: { paginationModel: { pageSize: 20 } } }}
            onRowClick={(p) => navigate(`/players/${p.id}`)}
            sx={{ cursor: 'pointer' }}
            disableRowSelectionOnClick
          />
        </>
      )}

      {players.isError && (
        <Typography color="error" sx={{ mt: 2 }}>Failed to load player data.</Typography>
      )}
    </Box>
  );
}
