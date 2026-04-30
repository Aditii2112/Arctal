# Arctal Bond Data Quality Findings

## Approach

I validated data quality using:
- Cross-table reconciliations (`issuances` vs `cat_allocations` and `geo_allocations`)
- Key integrity checks (`bond_id` uniqueness/completeness, orphan records)
- Statistical sanity checks (FX dispersion by currency, impact outliers)
- Completeness checks (missing values in critical fields)

This assessment prioritizes issues by likely downstream business impact (reporting accuracy, investor disclosures, and analytics reliability).

## Prioritized Findings

### P1 - Allocation totals do not reconcile to issuance totals

**What I found**
- `30` bonds where category allocations (`cat_allocations.post_allocation_USD` summed by `bond_id`) do not equal `issuances.total_USD_allocated` (tolerance: USD 1).
- Largest gap observed: `bond_id=10760` (`France`), difference of about `USD 18.1M`.

**Why this matters**
- Breaks core financial integrity assumptions.
- Can materially distort use-of-proceeds and category exposure reporting.

**What I need / proposed correction path**
- Confirm whether `total_USD_allocated` represents a snapshot date different from category allocations.
- If same reporting period, restate either category rows or issuance-level total.

---

### P1 - Geographic allocation totals do not reconcile to issuance totals

**What I found**
- `31` bonds where geographic allocations (`geo_allocations.allocation_USD` summed by `bond_id`) do not equal `issuances.total_USD_allocated` (tolerance: USD 1).
- Largest gap observed: `bond_id=10608` (`France`), difference about `USD 337.7M`.

**Why this matters**
- Geographic impact reporting can be materially misstated.
- Regulatory and investor reporting risk if totals are used externally.

**What I need / proposed correction path**
- Validate whether geography rows are intentionally partial coverage.
- If intended to be complete, enforce per-bond sum checks in ETL and correct source rows.

---

### P2 - Impact metrics show extreme outliers and possible unit inconsistency

**What I found**
- `impact_per_million_USD` has very high upper tail (`95th percentile ~91k`, `99th percentile ~10.1M`, max `~839M`).
- `50` duplicate records by (`bond_id`, `impact_metric`).
- `34` null values in `impact_per_million_USD`.
- `2` negative values in both `impact_value` and `impact_per_million_USD`.

**Why this matters**
- Outliers may indicate unit mismatches (e.g., tonnes vs kg), denominator issues, or data-entry errors.
- Duplicate metric rows can inflate aggregate impact estimates.

**What I need / proposed correction path**
- Add metric-specific unit dictionary and acceptable ranges.
- De-duplicate by (`bond_id`, `impact_metric`, reporting_period) or add explicit versioning field.
- Backfill/null-policy for missing `impact_per_million_USD`.

---

### P2 - FX consistency risk in select currencies

**What I found**
- Implicit FX (`bond_USD_amount / bond_amount`) has notable dispersion for:
  - `HKD` (std ~`0.5036`, count `3`)
  - `GBP` (std ~`0.0661`, count `7`)
  - `USD` (std ~`0.0299`, count `50`; expected near zero if same denomination logic)

**Why this matters**
- Could indicate mixed rate dates, stale conversion rates, or currency amount inconsistencies.

**What I need / proposed correction path**
- Compare implied rates to issuance-date market benchmarks within a tolerance band.
- Clarify whether USD amounts are booking-date converted or issuance-date converted.

---

### P3 - Coverage gaps in child tables

**What I found**
- `5` issuance bonds have no related `impacts` rows.
- `1` issuance bond has no related `geo_allocations` rows.
- `2` bonds have missing `maturity_date`.

**Why this matters**
- May be valid for new issuances, but should be explicit to avoid false negatives in reporting.

**What I need / proposed correction path**
- Add completeness flags (`is_impact_available`, `is_geo_allocation_complete`) and expected publication lag.
- Confirm whether missing maturity dates are perpetual/unknown instruments vs true data gaps.

## What Is Already Strong

- No missing `bond_id` values across all four tabs.
- No orphan child keys (all child `bond_id` values match existing issuance records).
- No duplicate `bond_id` values in `issuances`.

## Recommended Next 30 Minutes (Interview-Ready)

1. Prepare 2-3 concrete examples per P1 finding (bond IDs, exact differences, likely cause).
2. Explain one pragmatic remediation design:
   - Reconciliation checks in ingestion pipeline
   - Exception table for unresolved variances
   - Data contract for impact units and duplicate handling
3. Be explicit on trade-offs:
   - "Worth fixing now" (P1 totals)
   - "Investigate with domain owner" (impact unit outliers, FX policy)

## Files Used

- `bond_data.xlsx`
- `script.py` (audit code)
