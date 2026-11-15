# OLC CoreEngine Hardware Benchmark Report

## Hardware Profile
- **CPU Model**: AMD Ryzen 7 4800H with Radeon Graphics
- **CPU Cores/Threads**: 16
- **Total System RAM**: 30.76 GB
- **Storage Type**: SSD

## Workload Stress-Test Steps
| Universes | Target Hz | Effective Hz | Hz Retention | Status |
|-----------|-----------|--------------|--------------|--------|
| 4 | 44.0 | 44.16 Hz | 100.37% | PASS |
| 8 | 44.0 | 44.21 Hz | 100.47% | PASS |
| 16 | 44.0 | 44.14 Hz | 100.31% | PASS |
| 32 | 44.0 | 44.18 Hz | 100.4% | PASS |
| 64 | 44.0 | 44.17 Hz | 100.39% | PASS |
| 128 | 44.0 | 44.11 Hz | 100.26% | PASS |
| 192 | 44.0 | 44.08 Hz | 100.19% | PASS |
| 224 | 44.0 | 43.92 Hz | 99.83% | PASS |
| 240 | 44.0 | 43.81 Hz | 99.57% | PASS |
| 244 | 44.0 | 41.83 Hz | 95.06% | PASS |
| 246 | 44.0 | 43.54 Hz | 98.94% | PASS |
| 247 | 44.0 | 42.98 Hz | 97.68% | PASS |
| 248 | 44.0 | 41.69 Hz | 94.76% | FAIL |
| 256 | 44.0 | 39.19 Hz | 89.07% | FAIL |

## Final Performance Verdict
- **Maximum Stable Universes**: **247** (at >= 95% target frequency retention)
- **Recommended Production Limit**: **197** (with 20% safety margin)
