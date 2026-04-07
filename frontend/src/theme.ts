import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#00ff87' },
    secondary: { main: '#e90052' },
    background: {
      default: '#0e1726',
      paper: '#162136',
    },
    success: { main: '#00ff87' },
    error: { main: '#e90052' },
    warning: { main: '#f5a623' },
    text: {
      primary: '#e0e6ed',
      secondary: '#8899a6',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", sans-serif',
    h4: { fontWeight: 700 },
    h5: { fontWeight: 700 },
    h6: { fontWeight: 600 },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          border: '1px solid rgba(255,255,255,0.06)',
        },
      },
    },
  },
});

export default theme;
