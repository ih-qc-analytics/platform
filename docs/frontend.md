# Frontend

React SPA built with Vite and TypeScript. All report pages are client-side rendered; there is no server-side rendering.

**Entry point:** `frontend/src/main.tsx`
**Start command (dev):** `npm run dev` → `http://localhost:5173`

---

## Route Map

| Path | Component | Report |
|------|-----------|--------|
| `/` | — | Redirects to `/ventas-totales` |
| `/ventas-totales` | `VentasTotales.tsx` | Revenue summary + trend + geography |
| `/por-asesor` | `PorAsesor.tsx` | Per-seller table with product mix and KPIs |
| `/detalle-asesor` | `DetallePorAsesor.tsx` | Per-seller exam registrations and school breakdown |
| `/por-pais` | `PorPais.tsx` | Per-country table + slide-out detail panel |
| `/login` | `LoginPage.tsx` | Email/password login (public, no auth required) |

All routes except `/login` are wrapped in `ProtectedLayout`, which redirects unauthenticated users to `/login`.

---

## Component Structure

```
App.tsx
├── AppTopBar.tsx          — Navigation tabs, user menu, currency toggle (MXN/USD)
└── <report page>
      ├── FilterBar.tsx    — Date range, geo filters, search, advanced options
      └── <report content>
            ├── KPI cards
            ├── TrendLine.tsx / GeoBar.tsx   (charts)
            └── Data table or card grid
```

**`AppTopBar`** (`components/layout/AppTopBar.tsx`): Renders the nav tabs (one per report), the brand name, and a user dropdown (currency preference + sign out). The base currency preference is stored in localStorage and toggles between `MXN` and `USD`.

**`FilterBar`** (`components/filters/FilterBar.tsx`): Hosts the date range picker, multi-select geo filters (country → zone → state → city), a search field, and the `AdvancedOptionsPopover` which contains comparison mode controls. Filter state lives in the report page component and is passed down as props.

---

## Data Fetching

Data fetching uses **TanStack React Query** (`@tanstack/react-query`). Each report page has a custom hook in `src/hooks/useReports.ts`.

```ts
// Example: Por Asesor
const { data, isLoading, error } = useAsesorReport(filters)
```

**How it works:**
1. The hook calls the appropriate function from `src/api/reports.ts`
2. The API function calls `src/api/client.ts::apiFetch()`, which attaches the `Authorization` and `X-Currency` headers
3. React Query caches the result by the serialized filter object as the query key
4. When filters change, React Query fires a new fetch and keeps the previous data visible until the new data arrives (using `placeholderData: keepPreviousData`)

**Comparison mode fetching:** When `show_comparison=true` is in the filter state, the same single API call includes the comparison params (`comparison_mode`, `comparison_date_from`, `comparison_date_to`). The backend runs both the current and comparison queries and returns them together in one response — a `current` field and an optional `comparison` field. Deltas (% change) are then computed on the frontend using `getPercentChange()` from `src/lib/utils.ts`.

---

## Filter System

Filters are plain objects matching `src/types/index.ts` filter types (e.g. `AsesorFilters`, `PorPaisFilters`). They are:

1. **Stored in state** in the report page component via `useState`
2. **Passed to the hook** as the query dependency — any change triggers a re-fetch
3. **Serialized as query params** by the API functions in `src/api/reports.ts`

**Debouncing:** Text search fields use `useDebouncedValue()` (`src/hooks/useDebouncedValue.ts`) to delay the query by 300ms so the API isn't called on every keystroke.

**Geo filter cascade:** Country → Zone → State → City. Selecting a country clears zone/state/city. Filter options are fetched from `/filters/options` on mount and are not dependent on the current date range.

**Seller filter:** For Detalle Asesor, sellers are loaded from `/filters/sellers`. This is a flat list, not cascaded.

---

## Comparison Mode

Enabled via the `AdvancedOptionsPopover` in the `FilterBar`. When active:

- `show_comparison: true` is added to the filter object
- `comparison_mode` is one of `PREVIOUS_YEAR`, `PREVIOUS_PERIOD`, or `CUSTOM`
- For `CUSTOM`, `comparison_date_from` and `comparison_date_to` are also included

**What the response looks like:** `{ current: { ... }, comparison: { ... } | null }`. The `comparison` field is `null` when `show_comparison=false`.

**What renders in comparison mode:**
- KPI cards show the current value large, with the previous-period value in grey below it and a coloured percentage delta (green = positive, red = negative)
- Table cells stack: current value → previous value (grey, small) → % delta (coloured)
- The trend chart renders a second dashed line ("Comparativo") aligned by position to the current period's data points
- The Por País side panel shows a grey comparison value and % delta under each metric card

If `getPercentChange(current, previous)` returns `null` (previous is 0 or undefined), no percentage is shown — not a dash, just nothing.

---

## Currency Preference

The user's chosen base currency (MXN or USD) is persisted in `localStorage` under the key `base_currency`.

- **Reading/writing:** `src/lib/reportPreferences.ts` exposes `getBaseCurrency()` and `setBaseCurrency()`
- **Subscribing to changes:** `src/components/layout/AppTopBar.tsx` uses `useSyncExternalStore` so the UI updates instantly when the user toggles the currency without a full re-render
- **Sending to the backend:** `src/api/client.ts` reads the current value and includes it as `X-Currency: MXN` (or `USD`) on every request. The backend switches between `*_mxn` and `*_usd` columns based on this header.

---

## API Client

`src/api/client.ts` exports a single `apiFetch(path, options)` function used by all API calls.

It:
1. Reads the active Supabase session and extracts the JWT
2. Reads `localStorage` for the base currency preference
3. Attaches `Authorization: Bearer <token>` and `X-Currency: <currency>` headers
4. Throws a typed `ApiError` on non-2xx responses
5. If the response is `401`, calls `supabase.auth.signOut()` and redirects to `/login`

All API functions in `src/api/reports.ts` and `src/api/filters.ts` call `apiFetch` — they never call `fetch` directly.

---

## TypeScript Types

All types are in `src/types/index.ts`. They mirror the backend's Pydantic schemas exactly. When a backend schema changes, update the matching type here.

Key type groups:
- `*Filters` — request filter objects (e.g. `AsesorFilters`, `PorPaisFilters`)
- `*Response` — top-level API response shapes
- `*Base` — the main data object inside a response (current period)
- `*Row` — a single row in a paginated table
- `TrendPoint`, `GeoPoint` — chart data points
- `PDFKpiItem`, `PDFTable` — payload types for PDF exports

---

## Adding a New Report

1. **Types** — add `NewReportFilters`, `NewReportBase`, `NewReportResponse` to `src/types/index.ts`
2. **API call** — add `fetchNewReport(filters: NewReportFilters): Promise<NewReportResponse>` to `src/api/reports.ts` using `apiFetch`
3. **Hook** — add `useNewReport(filters)` to `src/hooks/useReports.ts` using `useQuery` with the filter object as the query key
4. **Component** — create `src/components/reports/NewReport.tsx`. Use an existing report component as a template. Compose `FilterBar` + your content.
5. **Route** — add the route to `src/App.tsx` and a nav tab to `AppTopBar.tsx`

---

## UI Component Library

UI primitives live in `src/components/ui/` and are generated by **shadcn/ui** (Radix UI + Tailwind). They are checked into the repo — do not re-generate them unless intentionally upgrading.

Available components: `Button`, `Badge`, `Card`, `Dialog`, `DropdownMenu`, `Input`, `Label`, `Popover`, `Select`, `Separator`, `Sheet` (slide-over panel), `Skeleton`, `Table`, `Tooltip`.

**Charts** use **Recharts** wrapped by the `ChartContainer` / `ChartTooltip` / `ChartLegend` components in `src/components/ui/chart.tsx` (also from shadcn/ui).

**Icons** come from `lucide-react`.

**Styling** is Tailwind CSS. The colour palette and design tokens are defined in `src/index.css` as CSS custom properties (`--background`, `--foreground`, `--card`, `--topbar`, `--chart-1`, etc.).
