# Frontend Redesign Plan

## Goal
Replace the current MUI-heavy frontend with a distinctive football-themed dashboard using Tailwind CSS and shadcn/ui components. Keep same page structure (8 pages), same API endpoints, same React/Vite/TypeScript stack.

## Design Direction
**Aesthetic**: Premium football broadcast / match-day stadium atmosphere. Dark, moody, with FPL brand colors as electric accents.

**Typography**: Oswald (display/headings - bold, condensed, sports broadcast) + Outfit (body/UI - geometric, modern, readable at data-table sizes).

**Color palette**:
- Background: Deep navy-black (#0a0e1a)
- Surface/cards: Lighter navy (#111827)
- Primary accent: FPL green (#00ff87)
- Secondary accent: FPL pink (#e90052)
- Tertiary: Gold (#f7c948)
- Text: Off-white (#e8edf3) / muted (#6b7a8d)

**Visual elements**: Subtle pitch-line grid texture, card accent stripes, broadcast-style stat cards, bold FDR color blocks, smooth animations.

## Package Changes
- **Install**: `@tanstack/react-table`
- **Uninstall**: `@mui/material`, `@mui/icons-material`, `@mui/x-data-grid`, `@emotion/react`, `@emotion/styled`

## New Components (10)
1. `AppLayout.tsx` - shadcn Sidebar layout replacing MUI Drawer
2. `PageHeader.tsx` - Reusable page title
3. `StatCard.tsx` - Broadcast-style stat card with accent stripe
4. `DataTable.tsx` - TanStack Table + shadcn Table (replaces all DataGrids)
5. `FDRBadge.tsx` - FDR difficulty badge (1-5 scale)
6. `FormBadge.tsx` - Player form indicator
7. `StatusBadge.tsx` - Player availability status
8. `FDRHeatmap.tsx` - Extracted heatmap component
9. `SearchInput.tsx` - Themed search input
10. `LoadingSkeleton.tsx` - Loading states

## Files to Delete
- `src/theme.ts` (MUI theme)
- `src/components/Layout.tsx` (replaced by AppLayout)

## Implementation Phases
1. **Foundation**: fonts, tailwind config, CSS variables, shadcn component variants
2. **Core Components**: All 10 new shared components
3. **App Shell**: App.tsx, delete MUI theme/layout
4. **Pages**: Rewrite all 8 pages (can parallelize)
5. **Cleanup**: Uninstall MUI, verify build

## Acceptance Criteria
1. Zero MUI imports remaining
2. `npm run build` succeeds
3. All 8 pages render and load data from API
4. Oswald headings, Outfit body text
5. Dark navy background, FPL green/pink accents
6. Collapsible sidebar with Lucide icons
7. All DataGrids replaced with TanStack Table
8. FDR heatmap renders with correct colors
9. Charts use new color scheme
10. Responsive down to 375px mobile
11. Hover/animation effects on cards and status indicators
12. All existing API calls and routes preserved
