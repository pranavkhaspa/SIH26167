# Task 12 — PDF assessment report exporter + offline demo mode

**Source:** `plan.md` Task 12 (P2). **In scope:** `backend/app/main.py` (new export endpoint),
a small report builder module, frontend "Export PDF" button, tests. **Untouched:**
`raster_engine.py`, `change_engine.py`, `vlm_adapter.py`, `.github/workflows/`, `.env`.

## Current state (verified)
- `/api/v1/query`, `/api/v1/analyze-change`, `/api/v1/demo/cloud-penetration`, `/api/v1/demo/change-detect`
  all return `{ intent, narrative, metrics, geojson, data_source }` from real rasters.
- Backend suite: 50 passed + 1 live-gated; frontend lint+build exit 0.
- VLM may be offline on judge stations (no internet / no key) — `SATQUERY_VLM_ENABLED=0` already
  falls back to deterministic narratives.

## Gaps to Fill
1. **Report exporter** (`backend/app/report_engine.py`, stdlib `reportlab` OR minimal hand-rolled
   PDF). Input: a stored `/api/v1/query` result dict. Output: A4 PDF with raster title, intent,
   metrics table (pixels / km² / hectares), EPSG:4326 polygon summary (feature count + first coords),
   and the (sanitized) narrative. Deterministic bytes; `HTTPException(400)` on malformed input.
2. **Endpoint** `GET /api/v1/export/{report_id}` or `POST /api/v1/export` (body = result JSON) →
   `application/pdf`, `Content-Disposition: attachment`. No synthetic data.
3. **Frontend**: "Export PDF" button on the Operational Inspection Report + bitemporal tab →
   POSTs the current result, downloads the blob, saves as `satquery-report-*.pdf`.
4. **Offline demo mode**: when `/api/v1/query` is unreachable (or `SATQUERY_OFFLINE=1`), keep the
   UI usable with the deterministic demo pair + cached last result (no fabricated numbers).

### Tests / gate
5. `POST /api/v1/export` with a real query result → 200, `application/pdf`, body starts with `%PDF`,
   report contains the exact metric values passed in. Malformed body → 400.
6. `cd backend && python -m pytest tests/ -q` green; `cd frontend && npm run lint && npm run build` green.

## Acceptance Criteria
- **AC-1:** Real, deterministic PDF bytes derive ONLY from the passed result (no fake metrics).
- **AC-2:** Export endpoint returns `application/pdf`; malformed input → 400.
- **AC-3:** UI Export button works on both VQA and Bi-Temporal tabs.
- **AC-4 (gate):** pytest + lint + build green; dep additions justified (prefer stdlib/no new deps
  if a hand-rolled PDF writer keeps the diff shortest).
- **AC-5:** No `|| true`, no secrets, EPSG:4326 polygons exported as real coordinates.

## Verification (implementer AND reviewer)
1. pytest (new export tests present + suite green), frontend lint+build.
2. Smoke: POST a `/api/v1/query` result to `/api/v1/export`, open the PDF, verify numbers match.
3. Switch on `SATQUERY_OFFLINE=1`, reload frontend → still navigable without backend.

## Definition of Done
All AC-1..AC-5; suite green; plan.md Task 12 → DONE + adjustment log; commit + push `staging`; PR → `main`; CI green.