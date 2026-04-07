import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Box, Typography, Tabs, Tab, Chip, Table, TableBody, TableCell,
  TableHead, TableRow, Paper, Skeleton, Alert,
} from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { api } from '@/lib/api';

// FDR colour scale — continuous gradient
const fdrBg = (fdr: number): string => {
  if (fdr <= 1.5) return '#00ff87';
  if (fdr <= 2.0) return '#2ddc73';
  if (fdr <= 2.5) return '#5ec960';
  if (fdr <= 3.0) return '#97b84e';
  if (fdr <= 3.5) return '#d4a43a';
  if (fdr <= 4.0) return '#f58a23';
  if (fdr <= 4.5) return '#e95035';
  return '#e90052';
};

const fdrTextColor = (fdr: number): string => (fdr > 3.5 ? '#fff' : '#000');

const predCols: GridColDef[] = [
  { field: 'gameweek', headerName: 'GW', width: 60, type: 'number' },
  { field: 'home_team', headerName: 'Home', flex: 1 },
  { field: 'away_team', headerName: 'Away', flex: 1 },
  {
    field: 'home_predicted_goals', headerName: 'Home xG', width: 100, type: 'number',
    valueFormatter: (v: number) => v?.toFixed(2) ?? '-',
  },
  {
    field: 'away_predicted_goals', headerName: 'Away xG', width: 100, type: 'number',
    valueFormatter: (v: number) => v?.toFixed(2) ?? '-',
  },
  {
    field: 'home_cs_pct', headerName: 'Home CS%', width: 100, type: 'number',
    valueFormatter: (v: number) => v != null ? `${v.toFixed(0)}%` : '-',
  },
  {
    field: 'away_cs_pct', headerName: 'Away CS%', width: 100, type: 'number',
    valueFormatter: (v: number) => v != null ? `${v.toFixed(0)}%` : '-',
  },
  { field: 'source', headerName: 'Source', width: 110 },
];

const oddsCols: GridColDef[] = [
  { field: 'gameweek', headerName: 'GW', width: 60 },
  { field: 'home_team', headerName: 'Home', flex: 1 },
  { field: 'away_team', headerName: 'Away', flex: 1 },
  {
    field: 'home_win', headerName: '1', width: 75, type: 'number',
    valueFormatter: (v: number) => v != null ? v.toFixed(2) : '-',
  },
  {
    field: 'draw', headerName: 'X', width: 75, type: 'number',
    valueFormatter: (v: number) => v != null ? v.toFixed(2) : '-',
  },
  {
    field: 'away_win', headerName: '2', width: 75, type: 'number',
    valueFormatter: (v: number) => v != null ? v.toFixed(2) : '-',
  },
  {
    field: 'over_2_5', headerName: 'O2.5', width: 80, type: 'number',
    valueFormatter: (v: number) => v != null ? v.toFixed(2) : '-',
  },
  {
    field: 'under_2_5', headerName: 'U2.5', width: 80, type: 'number',
    valueFormatter: (v: number) => v != null ? v.toFixed(2) : '-',
  },
  {
    field: 'btts_yes', headerName: 'BTTS Y', width: 85, type: 'number',
    valueFormatter: (v: number) => v != null ? v.toFixed(2) : '-',
  },
  {
    field: 'btts_no', headerName: 'BTTS N', width: 85, type: 'number',
    valueFormatter: (v: number) => v != null ? v.toFixed(2) : '-',
  },
];

function FDRHeatmap({ data }: { data: any }) {
  if (!data) return <Skeleton variant="rectangular" height={400} />;

  const gameweeks: number[] = data.gameweeks ?? [];
  const ratings: Record<string, Record<string, any>> = data.ratings ?? {};

  // Sort teams by average FDR (easiest first)
  const teams: any[] = [...(data.teams ?? [])].sort((a, b) => {
    const avgFdr = (t: any) => {
      const r = ratings[String(t.id)] ?? {};
      const vals = gameweeks
        .map((gw) => r[String(gw)]?.overall)
        .filter((v): v is number => v != null);
      return vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : 5;
    };
    return avgFdr(a) - avgFdr(b);
  });

  if (teams.length === 0) return <Alert severity="info">No FDR data available.</Alert>;

  return (
    <Box sx={{ overflowX: 'auto' }}>
      <Table
        size="small"
        sx={{
          '& td, & th': {
            p: '6px 8px',
            textAlign: 'center',
            border: '1px solid rgba(255,255,255,0.08)',
            whiteSpace: 'nowrap',
          },
        }}
      >
        <TableHead>
          <TableRow>
            <TableCell sx={{ textAlign: 'left !important', minWidth: 80, fontWeight: 700 }}>Team</TableCell>
            <TableCell sx={{ fontWeight: 700, minWidth: 55 }}>Avg</TableCell>
            {gameweeks.map((gw) => (
              <TableCell key={gw} sx={{ fontWeight: 700, minWidth: 70 }}>GW{gw}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {teams.map((team) => {
            const teamRatings = ratings[String(team.id)] ?? {};
            return (
              <TableRow key={team.id}>
                <TableCell sx={{ textAlign: 'left !important', fontWeight: 600 }}>{team.short_name}</TableCell>
                {(() => {
                  const vals = gameweeks
                    .map((gw) => teamRatings[String(gw)]?.overall)
                    .filter((v): v is number => v != null);
                  const avg = vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : 0;
                  return (
                    <TableCell sx={{
                      background: avg > 0 ? fdrBg(avg) : undefined,
                      color: avg > 0 ? fdrTextColor(avg) : 'text.disabled',
                      fontWeight: 700,
                      fontSize: 12,
                    }}>
                      {avg > 0 ? avg.toFixed(1) : '—'}
                    </TableCell>
                  );
                })()}
                {gameweeks.map((gw) => {
                  const entry = teamRatings[String(gw)];
                  if (!entry) {
                    return <TableCell key={gw} sx={{ color: 'text.disabled' }}>—</TableCell>;
                  }
                  const fdr = entry.overall ?? 3;
                  return (
                    <TableCell
                      key={gw}
                      sx={{
                        background: fdrBg(fdr),
                        color: fdrTextColor(fdr),
                        fontWeight: 700,
                        fontSize: 11,
                      }}
                    >
                      {entry.is_home ? '' : '@'}{entry.opponent}
                    </TableCell>
                  );
                })}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      <Box sx={{ display: 'flex', gap: 1, mt: 2, flexWrap: 'wrap' }}>
        {[
          { label: '1-2 Easy', bg: '#00ff87', color: '#000' },
          { label: '2-2.5', bg: '#5ec960', color: '#000' },
          { label: '2.5-3', bg: '#97b84e', color: '#000' },
          { label: '3-3.5', bg: '#d4a43a', color: '#000' },
          { label: '3.5-4', bg: '#f58a23', color: '#fff' },
          { label: '4+ Hard', bg: '#e90052', color: '#fff' },
        ].map((l) => (
          <Chip
            key={l.label}
            label={l.label}
            size="small"
            sx={{ bgcolor: l.bg, color: l.color, fontWeight: 700 }}
          />
        ))}
      </Box>
    </Box>
  );
}

export default function FixturesPage() {
  const [tab, setTab] = useState(0);

  const fdr = useQuery({ queryKey: ['fdr'], queryFn: () => api.getFDR() });
  const predictions = useQuery({
    queryKey: ['predictions'],
    queryFn: () => api.getPredictions(),
    enabled: tab === 1,
  });
  const odds = useQuery({
    queryKey: ['odds'],
    queryFn: () => api.getBettingOdds(),
    enabled: tab === 2,
  });

  const predRows = ((predictions.data as any[]) ?? []).map((r, i) => ({ ...r, _id: r.fixture_id ?? i }));
  const oddsRows = ((odds.data as any[]) ?? []).map((r, i) => ({ ...r, _id: r.fixture_id ?? i }));

  return (
    <Box>
      <Typography variant="h4" gutterBottom>Fixtures</Typography>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab label="FDR Heatmap" />
        <Tab label="Goal Predictions" />
        <Tab label="Betting Odds" />
      </Tabs>

      {tab === 0 && (
        fdr.isLoading
          ? <Skeleton variant="rectangular" height={400} />
          : <FDRHeatmap data={fdr.data} />
      )}

      {tab === 1 && (
        <DataGrid
          rows={predRows}
          columns={predCols}
          getRowId={(r) => r._id}
          autoHeight
          disableRowSelectionOnClick
          hideFooter
          loading={predictions.isLoading}
        />
      )}

      {tab === 2 && (
        <DataGrid
          rows={oddsRows}
          columns={oddsCols}
          getRowId={(r) => r._id}
          autoHeight
          disableRowSelectionOnClick
          hideFooter
          loading={odds.isLoading}
        />
      )}
    </Box>
  );
}
