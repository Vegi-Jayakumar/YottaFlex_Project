# DataFlow Performance & Optimization Note

## Measured Benchmarks
- **1,000 orders**: ~0.3 seconds.
- **100,000 orders**: ~3.0 - 3.4 seconds (RAM-backed SQLite reference execution).
- **Audit Logging**: Batched and optimized to minimize transaction overhead.
- **Vectorized Validation**: Uses pandas vectorized masks and finite checks (`np.isfinite`) for high-throughput data validation.
