# DataFlow Pipeline Architecture & Lineage

## Architecture Overview
The pipeline follows a modular ETL design:
1. **Discovery & Registration**: Discovers CSV files in raw storage, computes SHA-256 hashes, and registers them with `DISCOVERED` status before parsing.
2. **Ingestion & Validation**: Reads structured CSVs with explicit string dtypes, validates schema, ranges, finiteness (`np.isfinite`), and referential integrity. Distinct rejected rows are quarantined.
3. **Transformation**: Normalizes string whitespace/case, computes order totals, and prepares clean frames.
4. **Loading (Upsert)**: Safely loads dimension tables (`customers`, `products`) and fact tables (`orders`) using business-key upserts within transactions.
5. **Lineage & Reconciliation**: Records artifact-level dependency edges (`PRIMARY_SOURCE`, `PRICE_LOOKUP`, `REFERENCE_VALIDATION`), output checksums, and reconciliation summaries.
