import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Box, Typography, Button, Alert, Chip, Table, TableBody, TableCell, TableHead, TableRow, Paper } from '@mui/material';
import { Refresh } from '@mui/icons-material';
import { api } from '@/lib/api';

const statusColor = (status: string) => {
  if (status === 'a') return 'success';
  if (status === 'd') return 'warning';
  return 'error';
};

const formColor = (form: number) => {
  if (form >= 6) return '#00ff87';
  if (form >= 4) return '#f5a623';
  return '#e90052';
};

function PlayerTable({ players, title, dimmed }: { players: any[]; title: string; dimmed?: boolean }) {
  return (
    <Box sx={{ mb: 3, opacity: dimmed ? 0.75 : 1 }}>
      <Typography variant="h6" gutterBottom>{title}</Typography>
      <Paper>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Pos</TableCell>
              <TableCell>Player</TableCell>
              <TableCell>Team</TableCell>
              <TableCell align="right">Cost</TableCell>
              <TableCell align="right">Form</TableCell>
              <TableCell align="right">xPts GW</TableCell>
              <TableCell align="center">Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {players.map((p: any) => (
              <TableRow key={p.id} hover>
                <TableCell>{p.position}</TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    {p.web_name}
                    {p.is_captain && <Chip label="C" size="small" color="primary" sx={{ height: 18, fontSize: 10 }} />}
                    {p.is_vice_captain && <Chip label="V" size="small" color="secondary" sx={{ height: 18, fontSize: 10 }} />}
                  </Box>
                </TableCell>
                <TableCell>{p.team}</TableCell>
                <TableCell align="right">£{(p.cost || p.selling_price || 0).toFixed(1)}m</TableCell>
                <TableCell align="right">
                  <Typography sx={{ color: formColor(p.form || 0), fontWeight: 600 }}>
                    {(p.form || 0).toFixed(1)}
                  </Typography>
                </TableCell>
                <TableCell align="right">{(p.xpts_next_gw || 0).toFixed(1)}</TableCell>
                <TableCell align="center">
                  <Chip
                    label={p.status === 'a' ? 'Fit' : p.status === 'd' ? 'Doubt' : p.status?.toUpperCase() || 'A'}
                    size="small"
                    color={statusColor(p.status || 'a') as any}
                    variant="outlined"
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}

export default function MyTeamPage() {
  const qc = useQueryClient();
  const team = useQuery({ queryKey: ['team'], queryFn: () => api.getTeam() });
  const analysis = useQuery({ queryKey: ['teamAnalysis'], queryFn: () => api.getTeamAnalysis(5) });

  const teamData = team.data as any;
  const analysisData = analysis.data as any;

  const starters = teamData?.players?.filter((p: any) => p.is_starter) ?? [];
  const bench = teamData?.players?.filter((p: any) => !p.is_starter) ?? [];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">My Team</Typography>
        <Button
          startIcon={<Refresh />}
          variant="outlined"
          onClick={() => {
            qc.invalidateQueries({ queryKey: ['team'] });
            qc.invalidateQueries({ queryKey: ['teamAnalysis'] });
          }}
        >
          Refresh
        </Button>
      </Box>

      {team.isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load team data. Go to Settings and enter your FPL Team ID first.
        </Alert>
      )}

      {teamData && (
        <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
          <Chip label={`GW${teamData.gameweek}`} color="primary" />
          <Chip label={`${teamData.overall_points?.toLocaleString()} pts`} variant="outlined" />
          <Chip label={`Rank: ${teamData.overall_rank?.toLocaleString()}`} variant="outlined" />
          <Chip label={`Bank: £${(teamData.bank || 0).toFixed(1)}m`} variant="outlined" />
          <Chip label={`Free Transfers: ${teamData.free_transfers}`} variant="outlined" />
        </Box>
      )}

      {analysisData && (
        <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
          <Chip label={`Next GW xPts: ${(analysisData.projected_xi_gw1 || 0).toFixed(1)}`} color="success" />
          <Chip label={`3 GW xPts: ${(analysisData.projected_xi_3gw || 0).toFixed(1)}`} />
          <Chip label={`5 GW xPts: ${(analysisData.projected_xi_5gw || 0).toFixed(1)}`} />
          <Chip label={`Squad Strength: ${(analysisData.squad_strength || 0).toFixed(1)}`} variant="outlined" />
        </Box>
      )}

      <PlayerTable players={starters} title="Starting XI" />
      <PlayerTable players={bench} title="Bench" dimmed />

      {analysisData?.weak_spots && analysisData.weak_spots.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="h6" gutterBottom>Weak Spots</Typography>
          {analysisData.weak_spots.map((w: string, i: number) => (
            <Alert key={i} severity="warning" sx={{ mb: 1 }}>{w}</Alert>
          ))}
        </Box>
      )}
    </Box>
  );
}
