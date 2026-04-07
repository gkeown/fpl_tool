import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Box, Drawer, List, ListItemButton, ListItemIcon, ListItemText,
  Toolbar, AppBar, Typography, IconButton, useMediaQuery, useTheme,
} from '@mui/material';
import {
  Dashboard as DashboardIcon, Group, People, CalendarMonth,
  SwapHoriz, TrendingUp, Settings, Menu as MenuIcon, SportsSoccer,
} from '@mui/icons-material';

const DRAWER_WIDTH = 240;

const NAV = [
  { label: 'Dashboard', path: '/', icon: <DashboardIcon /> },
  { label: 'My Team', path: '/team', icon: <Group /> },
  { label: 'Players', path: '/players', icon: <People /> },
  { label: 'Fixtures', path: '/fixtures', icon: <CalendarMonth /> },
  { label: 'Transfers', path: '/transfers', icon: <SwapHoriz /> },
  { label: 'Prices', path: '/prices', icon: <TrendingUp /> },
  { label: 'Settings', path: '/settings', icon: <Settings /> },
];

export default function Layout() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const drawer = (
    <Box sx={{ overflow: 'auto' }}>
      <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
        <SportsSoccer sx={{ color: 'primary.main' }} />
        <Typography variant="h6" sx={{ color: 'primary.main', fontWeight: 800 }}>
          FPL Assistant
        </Typography>
      </Box>
      <List>
        {NAV.map((item) => (
          <ListItemButton
            key={item.path}
            selected={pathname === item.path}
            onClick={() => { navigate(item.path); setOpen(false); }}
            sx={{
              mx: 1, borderRadius: 2, mb: 0.5,
              '&.Mui-selected': { bgcolor: 'rgba(0,255,135,0.1)', color: 'primary.main' },
            }}
          >
            <ListItemIcon sx={{ color: pathname === item.path ? 'primary.main' : 'text.secondary', minWidth: 40 }}>
              {item.icon}
            </ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      {isMobile && (
        <AppBar position="fixed" sx={{ bgcolor: 'background.paper' }}>
          <Toolbar>
            <IconButton edge="start" onClick={() => setOpen(true)} sx={{ color: 'text.primary' }}>
              <MenuIcon />
            </IconButton>
            <SportsSoccer sx={{ color: 'primary.main', ml: 1, mr: 1 }} />
            <Typography variant="h6" sx={{ color: 'primary.main' }}>FPL Assistant</Typography>
          </Toolbar>
        </AppBar>
      )}
      <Drawer
        variant={isMobile ? 'temporary' : 'permanent'}
        open={isMobile ? open : true}
        onClose={() => setOpen(false)}
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': { width: DRAWER_WIDTH, bgcolor: 'background.paper', borderRight: '1px solid rgba(255,255,255,0.06)' },
        }}
      >
        {drawer}
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3, mt: isMobile ? 8 : 0, overflow: 'auto' }}>
        <Outlet />
      </Box>
    </Box>
  );
}
