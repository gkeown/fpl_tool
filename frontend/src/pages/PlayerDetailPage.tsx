import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Box, Typography, Card, CardContent, Chip, Skeleton, Grid,
  Table, TableBody, TableCell, TableHead, TableRow, Paper, Alert, Button,
} from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '@/lib/api';

const fdrCellStyle = (fdr: number): React.CSSProperties => {
  if (fdr <= 2) return { background: '#00ff87', color: '#000', fontWeight: 700 };
  if (fdr <= 3) return { background: '#97e27c', color: '#000', fontWeight: 700 };
  if (fdr <= 4) return { background: '#f5a623', color: '#000', fontWeight: 700 };
  return { background: '#e90052', color: '#fff', fontWeight: 700 };
};

function StatGrid({ data }: { data: Record<string, any> }) {
  return (
    <Grid container spacing={1}>
      {Object.entries(data).map(([key, val]) => (
        <Grid size={{ xs: 6, sm: 4 }} key={key}>
          <Box sx={{ p: 1, borderRadius: 1, bgcolor: 'rgba(255,255,255,0.04)' }}>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ textTransform: 'capitalize' }}>
              {key.replace(/_/g, ' ')}
            </Typography>
            <Typography variant="body1" fontWeight={600}>
              {val != null ? String(val) : '-'}
            </Typography>
          </Box>
        </Grid>
      ))}
    </Grid>
  );
}

export default function PlayerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: player, isLoading, isError } = useQuery({
    queryKey: ['player', id],
    queryFn: () => api.getPlayer(Number(id)),
    enabled: !!id,
  });

  if (isLoading) return <Skeleton variant="rectangular" height={400} sx={{ borderRadius: 2 }} />;
  if (isError) return <Alert severity="error">Failed to load player data.</Alert>;
  if (!player) return <Typography>Player not found</Typography>;

  const p = player as any;

  // recent_history: array of GW dicts
  const recentHistory: any[] = p.recent_history ?? [];
  // projections: dict with gw1_pts through gw5_pts, next_3gw_pts, next_5gw_pts
  const projections: any = p.projections ?? {};
  // upcoming_fixtures: array
  const upcomingFixtures: any[] = p.upcoming_fixtures ?? [];
  // set_piece_notes: array of strings
  const setPieceNotes: string[] = p.set_piece_notes ?? [];
  // season_stats: dict
  const seasonStats: any = p.season_stats ?? {};
  // defensive_stats: dict or null
  const defensiveStats: any = p.defensive_stats;

  const chartData = recentHistory.slice(-10);

  const projRows = [
    { label: 'Next GW', value: projections.gw1_pts },
    { label: 'Next 2 GW', value: projections.gw2_pts },
    { label: 'Next 3 GW', value: projections.gw3_pts },
    { label: 'Next 4 GW', value: projections.gw4_pts },
    { label: 'Next 5 GW', value: projections.gw5_pts },
    { label: '3 GW Total', value: projections.next_3gw_pts },
    { label: '5 GW Total', value: projections.next_5gw_pts },
  ].filter(r => r.value != null);

  const statusColor = p.status === 'a' ? 'success' : p.status === 'd' ? 'warning' : 'error';

  return (
    <Box>
      <Button startIcon={<ArrowBack />} onClick={() => navigate(-1)} sx={{ mb: 2 }}>
        Back
      </Button>

      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="h4">{p.web_name || p.name}</Typography>
          {p.name && p.web_name && p.name !== p.web_name && (
            <Typography variant="body2" color="text.secondary">{p.name}</Typography>
          )}
          <Box sx={{ display: 'flex', gap: 1, mt: 1, flexWrap: 'wrap' }}>
            <Chip label={p.team_short || p.team} variant="outlined" />
            <Chip label={p.position} />
            <Chip label={`£${parseFloat(p.cost) || 0}m`} variant="outlined" />
            <Chip
              label={`Form: ${parseFloat(p.form) || 0}`}
              color={parseFloat(p.form) >= 6 ? 'success' : parseFloat(p.form) < 3 ? 'error' : 'warning'}
            />
            <Chip
              label={p.status === 'a' ? 'Fit' : p.status === 'd' ? 'Doubtful' : (p.status || 'Unknown').toUpperCase()}
              color={statusColor as any}
              variant="outlined"
            />
          </Box>
          {p.news && (
            <Alert severity="warning" sx={{ mt: 1, py: 0.5 }}>
              {p.news}
            </Alert>
          )}
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* Season Stats */}
        {Object.keys(seasonStats).length > 0 && (
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Season Stats</Typography>
                <StatGrid data={seasonStats} />
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Defensive Stats */}
        {defensiveStats && Object.keys(defensiveStats).length > 0 && (
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Defensive Stats</Typography>
                <StatGrid data={defensiveStats} />
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Points Chart */}
        {chartData.length > 0 && (
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Recent Form (Last {chartData.length} GWs)</Typography>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis
                      dataKey="gameweek"
                      stroke="#8899a6"
                      tick={{ fontSize: 11 }}
                      label={{ value: 'GW', position: 'insideRight', offset: -5 }}
                    />
                    <YAxis stroke="#8899a6" tick={{ fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: '#162136', border: '1px solid rgba(255,255,255,0.1)' }}
                    />
                    <Line
                      type="monotone"
                      dataKey="total_points"
                      stroke="#00ff87"
                      strokeWidth={2}
                      dot={{ fill: '#00ff87', r: 3 }}
                      name="Points"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Projections */}
        {projRows.length > 0 && (
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Projected Points</Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Period</TableCell>
                      <TableCell align="right">xPts</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {projRows.map((r) => (
                      <TableRow key={r.label}>
                        <TableCell>{r.label}</TableCell>
                        <TableCell align="right">
                          <Typography fontWeight={600} color="primary.main">
                            {Number(r.value).toFixed(1)}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Upcoming Fixtures */}
        {upcomingFixtures.length > 0 && (
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Upcoming Fixtures</Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {upcomingFixtures.map((f: any, i: number) => {
                    const fdr = f.difficulty || f.fdr || f.overall_difficulty || 3;
                    const style = fdrCellStyle(fdr);
                    return (
                      <Chip
                        key={i}
                        label={`GW${f.gameweek || f.gw}: ${f.is_home ? '' : '@'}${f.team_short || f.opponent || f.team}`}
                        sx={{ bgcolor: style.background, color: style.color, fontWeight: 700 }}
                      />
                    );
                  })}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Recent History Table */}
        {recentHistory.length > 0 && (
          <Grid size={{ xs: 12 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Recent GW History</Typography>
                <Paper sx={{ overflowX: 'auto' }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>GW</TableCell>
                        <TableCell>Opponent</TableCell>
                        <TableCell align="right">Pts</TableCell>
                        <TableCell align="right">Mins</TableCell>
                        <TableCell align="right">G</TableCell>
                        <TableCell align="right">A</TableCell>
                        <TableCell align="right">CS</TableCell>
                        <TableCell align="right">Saves</TableCell>
                        <TableCell align="right">Bonus</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {recentHistory.slice(-10).reverse().map((gw: any, i: number) => (
                        <TableRow key={i} hover>
                          <TableCell>{gw.gameweek}</TableCell>
                          <TableCell>{gw.was_home ? 'H' : 'A'}</TableCell>
                          <TableCell align="right">
                            <Typography fontWeight={600} color={(gw.total_points || 0) >= 8 ? 'success.main' : 'text.primary'}>
                              {gw.total_points ?? '-'}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">{gw.minutes ?? '-'}</TableCell>
                          <TableCell align="right">{gw.goals_scored ?? '-'}</TableCell>
                          <TableCell align="right">{gw.assists ?? '-'}</TableCell>
                          <TableCell align="right">{gw.clean_sheets ?? '-'}</TableCell>
                          <TableCell align="right">{gw.saves ?? '-'}</TableCell>
                          <TableCell align="right">{gw.bonus ?? '-'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Paper>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Set Piece Notes */}
        {setPieceNotes.length > 0 && (
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Set-Piece Notes</Typography>
                {setPieceNotes.map((note: string, i: number) => (
                  <Typography key={i} variant="body2" sx={{ mb: 1, p: 1, borderRadius: 1, bgcolor: 'rgba(255,255,255,0.04)' }}>
                    {note}
                  </Typography>
                ))}
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}
