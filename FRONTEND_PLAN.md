# FPL Tool — Frontend Plan

## Architecture

```
┌─────────────────────────┐     ┌──────────────────────────┐
│   React + MUI Frontend  │────>│   FastAPI Backend         │
│   (designed in Lovable)  │<────│   (wraps existing code)   │
└─────────────────────────┘     └──────────┬───────────────┘
        Port 5173                    Port 8000
                                           │
                                    ┌──────┴──────┐
                                    │  Existing   │
                                    │  fpl/       │
                                    │  analysis/  │
                                    │  ingest/    │
                                    │  db/        │
                                    └─────────────┘
```

The existing analysis and ingest code is already clean and separated from the CLI.
FastAPI exposes the same data as REST endpoints. The React frontend consumes them.

## API Endpoints

### Players
- `GET /api/players/form?position=MID&max_cost=8.0&min_minutes=90&top=20` — form rankings
- `GET /api/players/search?q=Saka` — fuzzy name search
- `GET /api/players/{id}` — full player detail (stats, GW history, projections, FDR, set-pieces)
- `GET /api/players/differentials?max_ownership=10&position=MID&top=20` — differentials

### Team
- `GET /api/me/team` — current squad with form + projected points
- `GET /api/me/analyse?weeks=5` — full analysis (form, FDR, xPts, weak spots)
- `POST /api/me/login` — `{"team_id": 1234567}` — load team

### Fixtures
- `GET /api/fixtures?gameweek=32` — fixture list
- `GET /api/fixtures/difficulty?weeks=6` — FDR heatmap data
- `GET /api/fixtures/odds?gameweek=32` — betting odds

### Predictions
- `GET /api/predict/goals?gameweek=32` — predicted scorelines + CS%
- `GET /api/predict/cleansheets?gameweek=32&top=20` — CS rankings

### Transfers
- `GET /api/transfers/suggest?weeks=5&top=10` — transfer suggestions
- `GET /api/transfers/compare?player1=Saka&player2=Palmer` — head-to-head

### Captain
- `GET /api/captain/pick?top=5` — captain recommendations

### Prices
- `GET /api/prices/risers?top=20` — most transferred in
- `GET /api/prices/fallers?top=20` — most transferred out

### Data Management
- `GET /api/data/status` — ingest status per source
- `POST /api/data/refresh?source=all&force=false` — trigger refresh
- `GET /api/news` — latest FPL news headlines

### Set-Pieces
- `GET /api/players/setpieces?team=Arsenal` — set-piece taker notes

## Frontend Pages

### 1. Dashboard (`/`)
Overview page with cards:
- "My Team" summary (projected points next 1/3/5 GWs, squad strength)
- Top 3 captain recommendations with scores
- Next GW fixture predictions (scorelines + CS%)
- Latest 5 FPL news headlines
- Left sidebar navigation with icons

### 2. My Team (`/team`)
Full squad view:
- MUI DataGrid: Position, Player, Team, Cost, Form, xPts(1), xPts(3), xPts(5), Avg FDR, Status
- Bench separated visually from starting XI
- Summary row with projected points totals
- "Weak Spots" alert section (injuries, form, tough fixtures)
- Refresh button

### 3. Players (`/players`)
Player database:
- MUI DataGrid: Rank, Player, Team, Position, Cost, Form, xG/90, xA/90, Pts/90
- Filter bar: position dropdown, max cost slider, min minutes input
- Sortable by any column
- Click row to navigate to player detail
- Tab for "Differentials" (low-ownership picks)

### 4. Player Detail (`/players/:id`)
Single player view:
- Header: name, team, position, cost, FPL form
- Season stats grid (goals, assists, xG, xA, clean sheets, etc.)
- Defensive stats (DEFCON, CBI, recoveries, tackles) for DEF/MID
- Line chart of points over last 10 GWs (Recharts)
- Projected points table (next 5 GWs + cumulative)
- Set-piece notes
- Upcoming fixtures with color-coded FDR

### 5. Fixtures (`/fixtures`)
Fixture hub with tabs:
- Tab 1: FDR heatmap grid (teams as rows, GWs as columns, color-coded)
- Tab 2: Next GW predictions (home/away, predicted goals, CS%)
- Tab 3: Betting odds (H/D/A, O/U 2.5)

### 6. Transfers (`/transfers`)
Transfer planner:
- Transfer suggestions table: Out, In, delta value, cost impact, form change
- Player comparison: two search/select fields, side-by-side stats

### 7. Prices (`/prices`)
Price change tracker:
- Two tabs: Risers and Fallers
- MUI DataGrid: Player, Team, Pos, Price, Own%, Net Transfers, Pressure
- Color-coded net transfers

### 8. Settings (`/settings`)
Configuration:
- FPL Team ID input with "Load Team" button
- Data status table (source, status, records, last updated)
- "Refresh All Data" button with loading spinner

## Design Spec
- MUI dark theme (palette mode: "dark")
- Responsive — desktop and tablet
- Left sidebar navigation with icons
- MUI components: DataGrid, Card, Tabs, Chip, LinearProgress, Alert
- Color coding: green = good/easy, red = poor/hard, yellow = warnings
- FDR colors: 1-2 green, 2-3 light green, 3-4 yellow/orange, 4-5 red

## Lovable Prompt

Paste this into Lovable to generate the frontend:

> Build a Fantasy Premier League (FPL) assistant dashboard using React and MUI (Material UI) components. The app consumes a REST API at `http://localhost:8000/api`. Use MUI's dark theme.
>
> **Pages:**
>
> 1. **Dashboard** (`/`) — Overview page with:
>    - Card showing "My Team" summary (total projected points for next 1/3/5 GWs, squad strength)
>    - Card showing top 3 captain recommendations with scores
>    - Card showing next GW fixture predictions (predicted scorelines + CS%)
>    - Card showing latest 5 FPL news headlines
>    - Sidebar or top nav linking to all pages
>
> 2. **My Team** (`/team`) — Full squad view:
>    - MUI DataGrid table: Position, Player, Team, Cost, Form, xPts(1), xPts(3), xPts(5), Avg FDR, Status
>    - Bench separated visually from starting XI
>    - Summary row with projected points totals
>    - "Weak Spots" alert section below the table (list of concerns)
>    - Refresh button to reload team data
>
> 3. **Players** (`/players`) — Player database:
>    - MUI DataGrid with columns: Rank, Player, Team, Position, Cost, Form, xG/90, xA/90, Pts/90
>    - Filter bar: position dropdown (GKP/DEF/MID/FWD), max cost slider, min minutes input
>    - Sortable by any column
>    - Click a row to navigate to player detail page
>    - Tab for "Differentials" showing low-ownership picks
>
> 4. **Player Detail** (`/players/:id`) — Single player view:
>    - Header: name, team badge, position, cost, FPL form
>    - Season stats grid (goals, assists, xG, xA, clean sheets, etc.)
>    - Defensive stats table (DEFCON, CBI, recoveries, tackles) for DEF/MID
>    - Line chart of points over last 10 gameweeks (MUI/Recharts)
>    - Projected points table (next 5 GWs + cumulative)
>    - Set-piece notes section
>    - Upcoming fixtures with color-coded FDR
>
> 5. **Fixtures** (`/fixtures`) — Fixture hub:
>    - Tab 1: FDR heatmap grid (teams as rows, next 6 GWs as columns, color-coded cells)
>    - Tab 2: Next GW predictions table (home/away, predicted goals, CS%)
>    - Tab 3: Betting odds table (H/D/A, O/U 2.5)
>
> 6. **Transfers** (`/transfers`) — Transfer planner:
>    - Transfer suggestions table: Out player, In player, delta value, cost impact, form change
>    - Player comparison: two dropdowns to select players, side-by-side stat comparison with green highlighting for the winner
>
> 7. **Prices** (`/prices`) — Price changes:
>    - Two tabs: Risers and Fallers
>    - MUI DataGrid: Player, Team, Position, Price, Ownership%, Net Transfers, Pressure
>    - Color-coded net transfers (green positive, red negative)
>
> 8. **Settings** (`/settings`) — Configuration:
>    - Input for FPL Team ID with "Load Team" button
>    - Data status table (source, status, records, last updated, duration)
>    - "Refresh All Data" button with loading spinner
>
> **Design:**
> - MUI dark theme (palette mode: "dark")
> - Responsive — works on desktop and tablet
> - Left sidebar navigation with icons for each page
> - Use MUI components: DataGrid, Card, Tabs, Chip, LinearProgress, Alert
> - Color coding: green for good form/easy fixtures, red for poor form/hard fixtures, yellow for warnings

## Implementation Order

1. **Build the FastAPI API layer** — Python, wraps existing analysis/ingest code
2. **Generate frontend in Lovable** — paste the prompt above
3. **Wire together** — replace Lovable mock data with real API calls, add CORS

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + uvicorn |
| Frontend | React 18 + TypeScript |
| UI Components | MUI (Material UI) v5/v6 |
| Charts | Recharts |
| Data tables | MUI DataGrid |
| State management | React Query (TanStack Query) for API caching |
| Routing | React Router v6 |
| Build | Vite |
