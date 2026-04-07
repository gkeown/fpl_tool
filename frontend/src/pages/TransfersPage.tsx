import { useQuery } from '@tanstack/react-query';
import { Box, Typography, Chip, Alert, Table, TableBody, TableCell, TableHead, TableRow, Paper } from '@mui/material';
import { api } from '@/lib/api';

// /api/transfers/suggest response shape:
// rank, out_player, out_player_id, out_team, out_cost,
// in_player, in_player_id, in_team, in_cost,
// position, delta_value, out_form, in_form, out_fdr, in_fdr, budget_impact

const fdrColor = (fdr: number): string => {
  if (fdr <= 2) return '#00ff87';
  if (fdr <= 3) return '#f5a623';
  return '#e90052';
};

const formColor = (form: number): string => {
  if (form >= 70) return '#00ff87';
  if (form >= 50) return '#f5a623';
  return '#e90052';
};

export default function TransfersPage() {
  const suggestions = useQuery({
    queryKey: ['transfers'],
    queryFn: () => api.getTransferSuggestions({ top: '10' }),
  });

  const rows = (suggestions.data as any[]) ?? [];

  return (
    <Box>
      <Typography variant="h4" gutterBottom>Transfer Suggestions</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Recommended transfers based on form, fixture difficulty, and value.
      </Typography>

      {suggestions.isError && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Transfer suggestions unavailable — ensure you have loaded your team in Settings.
        </Alert>
      )}

      <Paper sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell align="center">#</TableCell>
              <TableCell>Out</TableCell>
              <TableCell>In</TableCell>
              <TableCell align="center">Pos</TableCell>
              <TableCell align="right">Cost Out</TableCell>
              <TableCell align="right">Cost In</TableCell>
              <TableCell align="right">Budget Impact</TableCell>
              <TableCell align="center">Form Out</TableCell>
              <TableCell align="center">Form In</TableCell>
              <TableCell align="center">FDR Out</TableCell>
              <TableCell align="center">FDR In</TableCell>
              <TableCell align="right">Delta Value</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((r: any) => (
              <TableRow key={r.rank} hover>
                <TableCell align="center">
                  <Typography fontWeight={700} color="text.secondary">{r.rank}</Typography>
                </TableCell>
                <TableCell>
                  <Box>
                    <Typography fontWeight={600} color="error.main">{r.out_player}</Typography>
                    <Typography variant="caption" color="text.secondary">{r.out_team}</Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  <Box>
                    <Typography fontWeight={600} color="success.main">{r.in_player}</Typography>
                    <Typography variant="caption" color="text.secondary">{r.in_team}</Typography>
                  </Box>
                </TableCell>
                <TableCell align="center">
                  <Chip label={r.position} size="small" variant="outlined" />
                </TableCell>
                <TableCell align="right">£{parseFloat(r.out_cost) || 0}m</TableCell>
                <TableCell align="right">£{parseFloat(r.in_cost) || 0}m</TableCell>
                <TableCell align="right">
                  <Typography
                    fontWeight={600}
                    color={(r.budget_impact || 0) >= 0 ? 'success.main' : 'error.main'}
                  >
                    {(r.budget_impact || 0) >= 0 ? '+' : ''}{r.budget_impact}
                  </Typography>
                </TableCell>
                <TableCell align="center">
                  <Chip
                    label={(r.out_form || 0).toFixed(1)}
                    size="small"
                    sx={{ bgcolor: `${formColor(r.out_form || 0)}22`, color: formColor(r.out_form || 0), fontWeight: 700, border: `1px solid ${formColor(r.out_form || 0)}` }}
                  />
                </TableCell>
                <TableCell align="center">
                  <Chip
                    label={(r.in_form || 0).toFixed(1)}
                    size="small"
                    sx={{ bgcolor: `${formColor(r.in_form || 0)}22`, color: formColor(r.in_form || 0), fontWeight: 700, border: `1px solid ${formColor(r.in_form || 0)}` }}
                  />
                </TableCell>
                <TableCell align="center">
                  <Chip
                    label={(r.out_fdr || 0).toFixed(1)}
                    size="small"
                    sx={{ bgcolor: fdrColor(r.out_fdr || 3), color: '#000', fontWeight: 700 }}
                  />
                </TableCell>
                <TableCell align="center">
                  <Chip
                    label={(r.in_fdr || 0).toFixed(1)}
                    size="small"
                    sx={{ bgcolor: fdrColor(r.in_fdr || 3), color: '#000', fontWeight: 700 }}
                  />
                </TableCell>
                <TableCell align="right">
                  <Typography
                    fontWeight={700}
                    color={(r.delta_value || 0) > 0 ? 'success.main' : 'error.main'}
                  >
                    {(r.delta_value || 0) > 0 ? '+' : ''}{(r.delta_value || 0).toFixed(1)}
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && !suggestions.isLoading && (
              <TableRow>
                <TableCell colSpan={12} align="center">
                  <Typography color="text.secondary" sx={{ py: 3 }}>No transfer suggestions available</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}
