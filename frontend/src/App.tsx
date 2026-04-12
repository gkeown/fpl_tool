import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
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

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/team" element={<MyTeamPage />} />
          <Route path="/players" element={<PlayersPage />} />
          <Route path="/players/:id" element={<PlayerDetailPage />} />
          <Route path="/fixtures" element={<FixturesPage />} />
          <Route path="/transfers" element={<TransfersPage />} />
          <Route path="/prices" element={<PricesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/leagues" element={<LeaguePage />} />
          <Route path="/leagues/:leagueId/team/:entryId" element={<OpponentTeamPage />} />
          <Route path="/scores" element={<ScoresPage />} />
          <Route path="/tables" element={<TablesPage />} />
          <Route path="/stats" element={<StatsPage />} />
          <Route path="/live-gw" element={<LiveGameweekPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </QueryClientProvider>
);

export default App;
