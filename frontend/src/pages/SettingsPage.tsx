import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box, Typography, TextField, Button, CircularProgress, Alert,
  Table, TableBody, TableCell, TableHead, TableRow, Paper, Chip,
} from '@mui/material';
import { Refresh } from '@mui/icons-material';
import { api } from '@/lib/api';

// /api/data/status response shape:
// source, status, records_upserted, started_at, finished_at,
// duration_secs, age_secs, error_message

function formatAge(secs: number): string {
  if (secs < 60) return `${Math.round(secs)}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  return `${Math.round(secs / 3600)}h ago`;
}

function formatDuration(secs: number): string {
  return secs != null ? `${secs.toFixed(1)}s` : '-';
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const [teamId, setTeamId] = useState('');

  const status = useQuery({
    queryKey: ['dataStatus'],
    queryFn: () => api.getDataStatus(),
  });

  // POST /api/me/login?team_id=123
  const loadTeam = useMutation({
    mutationFn: () => api.loadTeam(Number(teamId)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['team'] });
      qc.invalidateQueries({ queryKey: ['teamAnalysis'] });
    },
  });

  // POST /api/data/refresh
  const refreshAll = useMutation({
    mutationFn: () => api.refreshAll(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dataStatus'] });
    },
  });

  const statusRows = (status.data as any[]) ?? [];

  return (
    <Box>
      <Typography variant="h4" gutterBottom>Settings</Typography>

      {/* Team Login */}
      <Box sx={{ mb: 4, p: 3, border: '1px solid rgba(255,255,255,0.1)', borderRadius: 2 }}>
        <Typography variant="h6" gutterBottom>Load FPL Team</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Enter your FPL team ID to load your squad, transfers, and analysis.
          Your team ID is in the URL when you visit the FPL website (e.g. fantasy.premierleague.com/entry/<strong>123456</strong>/event/1).
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField
            label="FPL Team ID"
            value={teamId}
            onChange={(e) => setTeamId(e.target.value)}
            size="small"
            type="number"
            sx={{ width: 200 }}
            placeholder="e.g. 123456"
          />
          <Button
            variant="contained"
            onClick={() => loadTeam.mutate()}
            disabled={!teamId || loadTeam.isPending}
            startIcon={loadTeam.isPending ? <CircularProgress size={16} /> : null}
          >
            {loadTeam.isPending ? 'Loading...' : 'Load Team'}
          </Button>
        </Box>
        {loadTeam.isSuccess && (
          <Alert severity="success" sx={{ mt: 2 }}>Team loaded successfully! Your squad data is now available.</Alert>
        )}
        {loadTeam.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            Failed to load team. Check your team ID and try again.
          </Alert>
        )}
      </Box>

      {/* Data Status */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Data Status</Typography>
          <Button
            variant="outlined"
            color="primary"
            onClick={() => refreshAll.mutate()}
            disabled={refreshAll.isPending}
            startIcon={refreshAll.isPending ? <CircularProgress size={16} /> : <Refresh />}
            size="small"
          >
            {refreshAll.isPending ? 'Refreshing...' : 'Refresh All Data'}
          </Button>
        </Box>

        {refreshAll.isSuccess && (
          <Alert severity="success" sx={{ mb: 2 }}>All data sources refreshed successfully.</Alert>
        )}
        {refreshAll.isError && (
          <Alert severity="error" sx={{ mb: 2 }}>Refresh failed. Check the server logs.</Alert>
        )}

        <Paper>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Source</TableCell>
                <TableCell align="center">Status</TableCell>
                <TableCell align="right">Records</TableCell>
                <TableCell align="right">Duration</TableCell>
                <TableCell align="right">Last Run</TableCell>
                <TableCell>Error</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {statusRows.map((row: any) => (
                <TableRow key={row.source} hover>
                  <TableCell>
                    <Typography fontWeight={600}>{row.source}</Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Chip
                      label={row.status}
                      size="small"
                      color={row.status === 'success' ? 'success' : 'error'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell align="right">
                    {row.records_upserted != null ? row.records_upserted.toLocaleString() : '-'}
                  </TableCell>
                  <TableCell align="right">{formatDuration(row.duration_secs)}</TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" color="text.secondary">
                      {row.age_secs != null ? formatAge(row.age_secs) : '-'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {row.error_message ? (
                      <Typography variant="caption" color="error.main">{row.error_message}</Typography>
                    ) : (
                      <Typography variant="caption" color="text.disabled">—</Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {statusRows.length === 0 && !status.isLoading && (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography color="text.secondary" sx={{ py: 2 }}>No data status available</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>
      </Box>
    </Box>
  );
}
