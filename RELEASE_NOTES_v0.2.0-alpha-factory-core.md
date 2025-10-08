# v0.2.0-alpha-factory-core — 2025-10-07

## Summary
AlphaFactory core components are stable and tested (smoke + pytest green).

## Changes since
- fd00589 alpha-factory: enforce Series.name in sma_cross.compute(); settle hooks; refresh manifest - 2360e4c alpha-factory: fix invalid patch in sma_cross.compute(); set Series.name; settle hooks; refresh manifest - 5f67c70 alpha-factory: assign Series.name in all factors; pass smoke - 7a24918 alpha-factory: SMACross factory uses fast/slow kwargs; settle hooks; refresh manifest - 480ee82 alpha-factory: add SMACross=SmaCross alias (append-only); settle hooks; refresh manifest - 75391de alpha-factory: fix sma_slope.compute indentation & input normalization; settle hooks; refresh manifest - f7bbaa1 alpha-factory: robust input normalization & warm-up handling in sma_cross.compute(); settle hooks; refresh manifest - 42d4e4f alpha-factory: rsi_thresh accepts Series/DataFrame cleanly - 7e2ad66 alpha-factory: format examples/tests; refresh manifest - 24bec24 alpha-factory: settle formatting; refresh manifest - 462c156 alpha-factory: settle formatters; refresh manifest - 1adb17f dev: add repo_root .pth creator - d187134 hooks: add manifest hooks; refresh manifest - 84381da chore: settle hooks; refresh manifest - 0054ced manifest: refresh

## How to use
- Import \egistry\ from \src.alpha_factory\
- Available factors: \si_thresh_14_30_70\, \sma_cross_10_30\, \sma_slope_20_1\, \sma_slope_50_1\
