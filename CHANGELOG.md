# Release notes
## Top consensus (robust across bps & grids)
| fast | slow | robust | Sharpeμ | Sharpeσ | Calmarμ | obs |
|-----:|-----:|------:|--------:|--------:|--------:|----:|
| 10 | 75 | 4.30 | 4.30 | 0.00 | 28.18 | 4 |
| 20 | 75 | 3.57 | 3.57 | 0.00 | 26.72 | 4 |
| 10 | 50 | 3.11 | 4.67 | 1.56 | 20.43 | 6 |
| 15 | 100 | 1.93 | 1.93 | 0.00 | 13.26 | 4 |
| 40 | 200 | 1.02 | 1.02 | 0.00 | 5.74 | 4 |
| 15 | 75 | 0.85 | 0.85 | 0.00 | 4.93 | 4 |
| 5 | 100 | 0.67 | 0.67 | 0.00 | 3.20 | 4 |
| 5 | 75 | 0.52 | 0.52 | 0.00 | 2.53 | 4 |
| 20 | 50 | -0.16 | 2.49 | 2.65 | 10.95 | 6 |
| 10 | 100 | -0.38 | 1.57 | 1.95 | 8.33 | 10 |

## Per-bps stability (top by robust score)
| fast | slow |  bps | robust | Sharpeμ | Sharpeσ | grids |
|-----:|-----:|-----:|------:|--------:|--------:|------:|
| 10 | 75 | 0 | 4.30 | 4.30 | 0.00 | 1 |
| 10 | 75 | 2 | 4.30 | 4.30 | 0.00 | 1 |
| 10 | 75 | 5 | 4.30 | 4.30 | 0.00 | 1 |
| 10 | 75 | 25 | 4.30 | 4.30 | 0.00 | 1 |
| 20 | 75 | 0 | 3.57 | 3.57 | 0.00 | 1 |
| 20 | 75 | 2 | 3.57 | 3.57 | 0.00 | 1 |
| 20 | 75 | 5 | 3.57 | 3.57 | 0.00 | 1 |
| 20 | 75 | 25 | 3.57 | 3.57 | 0.00 | 1 |
| 10 | 50 | NA | 3.11 | 4.67 | 1.56 | 6 |
| 15 | 100 | 0 | 1.93 | 1.93 | 0.00 | 1 |

## Latest grid: `ma_grid_20251004_181028`
- Attached: `heatmap_sharpe.csv`
- Attached: `heatmap_calmar.csv`
![heatmap_sharpe.png](heatmap_sharpe.png)
![heatmap_calmar.png](heatmap_calmar.png)

## Included artifacts
- `all_grids_combined.csv`
- `grid_stability_by_bps.csv`
- `best_params_consensus.csv`
- `ma_grid_20251004_181028\heatmap_sharpe.csv`
- `ma_grid_20251004_181028\heatmap_calmar.csv`
- `ma_grid_20251004_181028\heatmap_sharpe.png`
- `ma_grid_20251004_181028\heatmap_calmar.png`
