import { useQuery } from '@tanstack/react-query';
import { Box, Card, CardContent, Typography, Chip, Skeleton, Alert, Grid } from '@mui/material';
import { api } from '@/lib/api';

function StatCard({ title, children, loading }: { title: string; children: React.ReactNode; loading?: boolean }) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="h6" gutterBottom sx={{ color: 'text.secondary', fontSize: 14, textTransform: 'uppercase', letterSpacing: 1 }}>
          {title}
        </Typography>
        {loading ? <Skeleton variant="rectangular" height={100} /> : children}
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const team = useQuery({ queryKey: ['team'], queryFn: () => api.getTeam() });
  const captains = useQuery({ queryKey: ['captains'], queryFn: () => api.getCaptains() });
  const predictions = useQuery({ queryKey: ['predictions'], queryFn: () => api.getPredictions() });
  const news = useQuery({ queryKey: ['news'], queryFn: () => api.getNews() });

  // Compute projected totals from team players
  const starters = (team.data as any)?.players?.filter((p: any) => p.is_starter) || [];
  const projected1 = starters.reduce((s: number, p: any) => s + (p.xpts_next_gw || 0), 0);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>Dashboard</Typography>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 6 }}>
          <StatCard title="My Team Summary" loading={team.isLoading}>
            {team.data && (
              <Box>
                <Box sx={{ display: 'flex', gap: 3, mb: 2 }}>
                  <Box>
                    <Typography variant="h3" sx={{ color: 'primary.main' }}>{projected1.toFixed(1)}</Typography>
                    <Typography variant="caption" color="text.secondary">Next GW xPts</Typography>
                  </Box>
                  <Box>
                    <Typography variant="h4" color="text.secondary">{(team.data as any).overall_points}</Typography>
                    <Typography variant="caption" color="text.secondary">Total Points</Typography>
                  </Box>
                  <Box>
                    <Typography variant="h4" color="text.secondary">{(team.data as any).overall_rank?.toLocaleString()}</Typography>
                    <Typography variant="caption" color="text.secondary">Overall Rank</Typography>
                  </Box>
                </Box>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Chip label={`Bank: £${((team.data as any).bank || 0).toFixed(1)}m`} variant="outlined" size="small" />
                  <Chip label={`FT: ${(team.data as any).free_transfers}`} variant="outlined" size="small" />
                  <Chip label={`GW${(team.data as any).gameweek}`} color="primary" size="small" />
                </Box>
              </Box>
            )}
            {team.isError && <Alert severity="error">Failed to load team data. Run 'fpl me login' first.</Alert>}
          </StatCard>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <StatCard title="Captain Picks" loading={captains.isLoading}>
            {(captains.data as any[])?.slice(0, 3).map((c: any, i: number) => (
              <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 1, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                <Box>
                  <Typography fontWeight={700}>{i === 0 ? '👑 ' : ''}{c.player}</Typography>
                  <Typography variant="caption" color="text.secondary">{c.team} · {c.fixture}</Typography>
                </Box>
                <Chip label={(c.captain_score || 0).toFixed(1)} color={i === 0 ? 'primary' : 'default'} size="small" />
              </Box>
            ))}
            {captains.isError && <Alert severity="warning">No captain data</Alert>}
          </StatCard>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <StatCard title="Next GW Predictions" loading={predictions.isLoading}>
            {(predictions.data as any[])?.map((f: any, i: number) => (
              <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.75, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                <Typography variant="body2">{f.home_team} vs {f.away_team}</Typography>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  <Chip label={`${(f.home_predicted_goals || 0).toFixed(1)} - ${(f.away_predicted_goals || 0).toFixed(1)}`} size="small" variant="outlined" />
                  <Typography variant="caption" color="text.secondary">CS: {f.home_cs_pct?.toFixed(0)}%/{f.away_cs_pct?.toFixed(0)}%</Typography>
                </Box>
              </Box>
            ))}
          </StatCard>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <StatCard title="FPL News" loading={news.isLoading}>
            {(news.data as any[])?.slice(0, 5).map((n: any, i: number) => (
              <Box key={i} sx={{ py: 0.75, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                <Typography
                  variant="body2"
                  fontWeight={600}
                  component="a"
                  href={n.link}
                  target="_blank"
                  rel="noopener"
                  sx={{ color: 'text.primary', textDecoration: 'none', '&:hover': { color: 'primary.main' } }}
                >
                  {n.title}
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block">{n.published}</Typography>
              </Box>
            ))}
          </StatCard>
        </Grid>
      </Grid>
    </Box>
  );
}
