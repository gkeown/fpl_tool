import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { isLoggedIn, isAdmin } from "./lib/auth";
import AppLayout from "./components/AppLayout";
import LoginPage from "./pages/LoginPage";
import GuestSetupPage from "./pages/GuestSetupPage";
import DashboardPage from "./pages/DashboardPage";
import MyTeamPage from "./pages/MyTeamPage";
import PlayersPage from "./pages/PlayersPage";
import PlayerDetailPage from "./pages/PlayerDetailPage";
import FixturesPage from "./pages/FixturesPage";
import TransfersPage from "./pages/TransfersPage";
import PricesPage from "./pages/PricesPage";
import SettingsPage from "./pages/SettingsPage";
import LeaguePage from "./pages/LeaguePage";
import OpponentTeamPage from "./pages/OpponentTeamPage";
import ScoresPage from "./pages/ScoresPage";
import TablesPage from "./pages/TablesPage";
import StatsPage from "./pages/StatsPage";
import LiveGameweekPage from "./pages/LiveGameweekPage";
import MatchDetailPage from "./pages/MatchDetailPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function RequireAuth({ children }: { children: React.ReactNode }) {
  return isLoggedIn() ? <>{children}</> : <Navigate to="/login" replace />;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />;
  if (!isAdmin()) return <Navigate to="/" replace />;
  return <>{children}</>;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/team" element={<MyTeamPage />} />
          <Route path="/setup" element={<GuestSetupPage />} />
          <Route path="/players" element={<PlayersPage />} />
          <Route path="/players/:id" element={<PlayerDetailPage />} />
          <Route path="/leagues" element={<LeaguePage />} />
          <Route path="/leagues/:leagueId/team/:entryId" element={<OpponentTeamPage />} />
          <Route path="/scores" element={<ScoresPage />} />
          <Route path="/tables" element={<TablesPage />} />
          <Route path="/stats" element={<StatsPage />} />
          <Route path="/live-gw" element={<LiveGameweekPage />} />
          <Route path="/match/:leagueSlug/:fixtureId" element={<MatchDetailPage />} />
          {/* Admin-only routes */}
          <Route path="/fixtures" element={<RequireAdmin><FixturesPage /></RequireAdmin>} />
          <Route path="/transfers" element={<RequireAdmin><TransfersPage /></RequireAdmin>} />
          <Route path="/prices" element={<RequireAdmin><PricesPage /></RequireAdmin>} />
          <Route path="/settings" element={<RequireAdmin><SettingsPage /></RequireAdmin>} />
        </Route>
      </Routes>
    </BrowserRouter>
  </QueryClientProvider>
);

export default App;
