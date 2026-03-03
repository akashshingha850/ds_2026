# Distributed Detection System — Deep Log Analysis

**Date of experiments**: 2026-03-02  
**Analyst**: Generated from raw logs on 2026-03-03

---

## System Architecture Recap

| Role | Service | Description |
|------|---------|-------------|
| **Alert Aggregator** | `pi3-alert` | Correlates motion images with detection results, fires Telegram alerts |
| **Motion Detection** | `pi{N}-motion` | Captures frames on motion, publishes image + image_id |
| **COCO Detection** | `pi4 / pi3` | YOLOv8n NCNN object detection (person, car, fire hydrant, bus…) |
| **Fire Detection** | `pi4 / pi3` | YOLO-fire NCNN fire/smoke detection |
| **System Monitor** | `pi{N}-system_monitor` | 1 Hz CPU, memory, temp, disk, network telemetry |

Communication is ZeroMQ pub/sub (TCP). pi3 is always the alert aggregator.

---

## Scenarios Tested

| Scenario | Nodes active | pi3 role(s) | Motion source |
|----------|-------------|-------------|---------------|
| **A** | pi3 + pi4 + pi5 | Alert only | pi5-motion |
| **B1** | pi3 + pi5 | Alert + Detection (local) | pi3-motion |
| **B2** | pi3 + pi4 | Alert + Detection (local) | pi3-motion |

> In Scenarios B1 and B2, pi3 must co-locate alert aggregation with detection models, drastically increasing its load.

---

## 1. End-to-End Performance Comparison

### 1.1 Pipeline Latency (pi3 alert-node log)

| Metric | Scenario A | Scenario B1 | Scenario B2 |
|--------|-----------|------------|------------|
| Observation window | 95.7 s | 100.5 s | 99.6 s |
| Images processed | 55 | 49 | 60 |
| Throughput | **0.57 img/s** | 0.49 img/s | 0.60 img/s |
| Images with detections | **30 / 55 (54.5%)** | 12 / 49 (24.5%) | 5 / 60 (8.3%) |
| Alerts fired | **7** | 6 | 3 |
| Telegram confirmations | 7 / 7 | 6 / 6 | 3 / 3 |
| Lost / orphan events | 67 | 76 | **108** |

### 1.2 Latency Breakdown

| Latency Metric | Scenario A | Scenario B1 | Scenario B2 |
|----------------|-----------|------------|------------|
| **Queue Age avg** | 0.478 s | 1.775 s | 2.312 s |
| Queue Age max | 2.116 s | 2.985 s | 4.336 s |
| Queue Age p95 | 1.375 s | 2.835 s | 3.301 s |
| **Detection Lat avg** | 0.135 s | 1.039 s | 1.240 s |
| Detection Lat max | 1.163 s | 2.425 s | 2.090 s |
| Detection Lat p95 | 0.864 s | 2.390 s | 2.090 s |
| **E2E Lat avg** (recv→dispatch) | **0.207 s** | 1.145 s | 1.333 s |
| E2E Lat max | 1.189 s | 2.544 s | 2.114 s |
| E2E Lat p95 | 0.871 s | 2.406 s | 2.114 s |

> **Note**: *E2E Lat* = alert-coordinator recv → dispatch (Stage 2+3). *Queue Age* = full pipeline from motion publish → dispatch (Stage 1+2+3 + coordinator queue wait). Use Queue Age as the true system-level end-to-end latency.
>
> **Key insight**: Scenario A total pipeline (Queue Age) is **4.8× faster** than B2 (0.478 s vs 2.312 s). The alert-coordinator recv-to-dispatch E2E is **6.4× faster** (0.207 s vs 1.333 s). The distributed model fully isolates detection compute from the alert correlator.

---

## 2. Resource Utilisation

### 2.1 Scenario A — pi3 + pi4 + pi5

| Node | Avg CPU | Peak CPU | Avg Mem | Avg Temp | Peak Temp |
|------|---------|----------|---------|----------|-----------|
| **pi3** (alert only) | **3.8%** | 53.3% | 35.9% | 40.8°C | 47.8°C |
| **pi4** (COCO detect) | 12.2% | 83.6% | 18.0% | 60.8°C | 68.2°C |
| **pi5** (motion/cam) | 19.1% | 77.5% | 15.0% | 55.6°C | 63.9°C |

- pi3 is **largely idle** — alert aggregation alone is lightweight; avg CPU under 4%.
- pi4 peaks at 83.6% CPU during inference bursts but returns to idle between frames.
- pi5 sustains 19% average running motion detection and frame publishing.
- All nodes stay well within thermal safety margins (< 70°C).

### 2.2 Scenario B1 — pi3 + pi5 (pi4 absent)

| Node | Avg CPU | Peak CPU | Avg Mem | Avg Temp | Peak Temp |
|------|---------|----------|---------|----------|-----------|
| **pi3** (alert + detect) | **72.6%** | 95.1% | 68.9% | 60.6°C | 65.0°C |
| **pi5** (idle-ish) | 6.6% | 77.1% | 32.6% | 50.1°C | 57.9°C |

- pi3 is **critically overloaded** — average 72.6% CPU, peaking at 95.1%.
  Running alert + COCO + fire detection models on the same Raspberry Pi saturates all cores.
- Memory usage climbs to 68.9% average (peak 77.9%) — only ~210 MB headroom before OOM risk.
- pi5 is nearly idle; its processing capacity is wasted.
- Temperature of pi3 rises to 60–65°C, entering thermal throttle territory for Pi hardware.

### 2.3 Scenario B2 — pi3 + pi4 (pi5 absent)

| Node | Avg CPU | Peak CPU | Avg Mem | Avg Temp | Peak Temp |
|------|---------|----------|---------|----------|-----------|
| **pi3** (alert + motion + detect) | **64.5%** | 94.6% | 53.2% | 59.5°C | 65.5°C |
| **pi4** (COCO detect) | 16.3% | 91.8% | 22.9% | 59.2°C | 70.1°C |

- pi3 remains heavily loaded (64.5% avg, 94.6% peak) running motion detection + alert.
- pi4 now helps with COCO detection but has no fire-model offload path.
- Disk I/O on pi3 is dramatically higher: **avg 1,286 KB/s read, 2,733 KB/s write** (vs near-zero in Scenario A), suggesting model data swapping or heavy log flushing under pressure.
- pi4 peaks at 70.1°C — approaching the Raspberry Pi thermal limit.

---

## 3. Detection Quality Analysis

### 3.1 Detection Rate vs Node Configuration

```
Scenario A  (3 nodes):  54.5% of frames contain at least one detection
Scenario B1 (2 nodes):  24.5% of frames contain at least one detection
Scenario B2 (2 nodes):   8.3% of frames contain at least one detection
```

The detection rate collapse in B1/B2 is caused by **inference backpressure**:
when pi3 is saturated, queued images expire or are dropped before detection completes,
resulting in `No pending event found` orphan messages (67 → 76 → 108).

### 3.2 Inference Latency per Model

| Scenario | Node | Model | Images | Infer avg (ms) | Infer max (ms) | Infer p95 (ms) | Decode avg (ms) |
|----------|------|-------|--------|---------------|---------------|----------------|----------------|
| **A** | pi4 | COCO | 61 | **418.3** | 819.5 | 454.5 | 32.9 |
| **A** | pi5 | Fire | 61 | **228.3** | 452.3 | 359.8 | 18.2 |
| **B1** | pi5 | COCO | 54 | **155.3** | 655.7 | 426.3 | 18.7 |
| **B1** | pi5 | Fire | 54 | **149.5** | 710.8 | 412.2 | 19.6 |
| **B2** | pi4 | COCO | 63 | **955.1** | 2291.4 | 1344.3 | 37.6 |
| **B2** | pi4 | Fire | 63 | **944.8** | 2212.7 | 1296.0 | 38.8 |

Key observations:
- **B1 inference (pi5, co-located) is faster than A/pi4 dedicated**: Models on pi5 run COCO in 155 ms vs 418 ms on pi4. This shows pi5 has faster inference cores; the bottleneck in B1 is pi3 I/O, not the detector.
- **B2 inference (pi4, co-located dual) is 2.3–4.1× slower than A**: Co-location of both COCO and Fire on pi4 causes severe CPU contention — COCO degrades from 418→955 ms (+128%), Fire from 228→945 ms (+314%).
- **Decode time is proportional to inference load**: pi4 in B2 spends 37–39 ms on JPEG decode vs 18–33 ms in other scenarios, indicating CPU starvation during I/O phases too.
- **High p95 in B1**: Both models show p95 ≈ 412–426 ms despite avg ≈ 150–155 ms, indicating occasional pi5 bursts (when co-located services compete). Variance is highest in B1 (wide IQR).

### 3.3 Alert Classes Detected

**Scenario A** (7 alerts — most diverse):
- `car, fire hydrant, person` — COCO
- `person` — COCO
- `car, person` — COCO
- `bus, person` — COCO
- `fire` — fire model
- `fire, smoke` — fire model
- `smoke` — fire model

**Scenario B1** (6 alerts):
- `person, truck`, `person, traffic light`, `person`, `car, person` — COCO
- `smoke`, `fire, smoke` — fire model

**Scenario B2** (3 alerts — least sensitive):
- `bicycle, person, truck` — COCO
- `smoke`, `fire, smoke` — fire model

> Scenario A correctly detects nearly twice as many events per unit time as B1, and **produces 7× more detection-positive frames** relative to B2. Fire/smoke detections appear across all scenarios.

---

## 4. Lost / Orphan Event Analysis

`No pending event found` messages indicate a detection result arrived after the corresponding image was already evicted from the correlation queue (or vice versa). This is a signal of queue saturation.

| Scenario | Orphan events | Lost rate (per image) |
|----------|--------------|----------------------|
| A        | 67           | 1.22 / image |
| B1       | 76           | 1.55 / image |
| B2       | 108          | 1.80 / image |

The orphan rate grows monotonically as compute is consolidated — a direct effect of detection inference competing with alert I/O on the same process/CPU.

---

## 5. Clock Skew Observation

In all scenarios, **negative detection latencies** appear (e.g., −1.323 s in A, −1.151 s in B1, −0.571 s in B2). This occurs when the `Detection TS` timestamp (set on a remote node) is earlier than the `Recv TS` (set on pi3), revealing **NTP clock drift** between nodes of up to ~1.3 seconds. This does not affect system correctness but makes latency metrics slightly noisy — true detection latency should be interpreted using absolute deltas only.

---

## 6. Network Utilisation

All scenarios show extremely low network bandwidth usage:

| Direction | All scenarios |
|-----------|--------------|
| Upload (avg) | ~0.1 KB/s |
| Download (avg) | ~0.1 KB/s |
| Peak upload | 0.3 KB/s |
| Peak download | 1.5–1.8 KB/s |

The ZeroMQ local-network transport is not a bottleneck. The system is entirely compute-bound.

---

## 7. Telegram Alert Reliability

All fired alerts were successfully delivered via Telegram in every scenario:

| Scenario | Alerts fired | Telegram 200 OK | Reliability |
|----------|-------------|----------------|-------------|
| A | 7 | 7 | **100%** |
| B1 | 6 | 6 | **100%** |
| B2 | 3 | 3 | **100%** |

Alert send-to-Telegram latency was consistent at ~1.7 s (HTTP round-trip).

---

## 8. Key Findings & Recommendations

### 8.1 Findings

| # | Finding | Severity |
|---|---------|---------|
| 1 | Scenario A total E2E (Queue Age) is **4.8× lower** than B2 (0.478 s vs 2.312 s); Detection E2E is **6.4×** lower (0.207 s vs 1.333 s) | Critical |
| 2 | pi3 CPU saturates at **72–95%** when co-located with detection models | Critical |
| 3 | Detection rate collapses from **54.5% → 8.3%** as nodes are removed | High |
| 4 | Orphan/lost events increase **61%** (67 → 108) correlating with pi3 overload | High |
| 5 | pi3 memory in B1 peaks at **77.9%** — OOM risk under sustained load | High |
| 6 | pi4 reaches **70.1°C** in B2 — at thermal throttle threshold | Medium |
| 7 | Disk I/O on pi3-B2 is **849× higher** than A — likely model-file swapping | Medium |
| 8 | **NTP drift** of up to 1.3 s between nodes distorts latency metrics | Low |
| 9 | Network bandwidth is negligible — not a scalability bottleneck | Info |
| 10 | Telegram delivery has **100% reliability** across all scenarios | Info |

### 8.2 Recommendations

1. **Always run Scenario A (3-node minimum)** — the distributed topology is the only configuration that keeps pi3 within safe operating limits (< 5% avg CPU) while maintaining acceptable detection rates.

2. **Add a detection queue depth metric** — the `No pending event found` counter is a leading indicator of overload. Alert when orphan rate exceeds ~1.0/image.

3. **Consider model quantisation / batching on pi4** — pi4 peaks at 83.6% CPU under YOLO inference. Running NCNN models in INT4 or batching 2 frames could reduce peak load and temp below 60°C.

4. **Implement NTP healthcheck** — enforce `chronyc tracking` or `timedatectl` verification at startup to reduce clock skew and improve latency measurement accuracy.

5. **Memory guard on pi3 in degraded modes** — if `available_memory < 200 MB`, disable fire model and fallback to COCO only to avoid OOM kill in B1-equivalent failure modes.

6. **Add pi4 thermal fan control** — peak temperature of 70.1°C in B2 is at the Raspberry Pi OS thermal throttle boundary. Active cooling or a lower inference frequency cap should be applied.

7. **Tune correlation queue timeout** — with Scenario A's avg E2E of 0.207 s but B2's 4.2 s max, a single queue timeout value cannot serve all scenarios. Make it configurable per deployment topology.

---

## 9. Summary Table

| KPI | Scenario A ✅ | Scenario B1 ⚠️ | Scenario B2 ❌ |
|-----|-------------|--------------|--------------|
| Queue Age / total E2E (avg) | **0.478 s** | 1.775 s | 2.312 s |
| Queue Age / total E2E (p95) | **1.375 s** | 2.835 s | 3.301 s |
| Alert recv→dispatch E2E (avg) | **0.207 s** | 1.145 s | 1.333 s |
| Alert recv→dispatch E2E (p95) | **0.871 s** | 2.406 s | 2.114 s |
| Detection rate | **54.5%** | 24.5% | 8.3% |
| Alerts fired | **7** | 6 | 3 |
| pi3 avg CPU | **3.8%** | 72.6% | 64.5% |
| pi3 avg mem | **35.9%** | 68.9% | 53.2% |
| pi3 avg temp | **40.8°C** | 60.6°C | 59.5°C |
| Lost events | **67** | 76 | 108 |
| Telegram reliability | 100% | 100% | 100% |

---

## 10. Per-Stage Computation Delay Breakdown

Each image processed by the alert pipeline passes through three measurable stages:

```
[Camera / Motion]
      │
      │◄── Stage 1: Transmission delay (Event TS → Recv TS)
      │    Network + ZeroMQ pub/sub latency from source node to pi3
      ▼
[pi3 Alert Node — image received]
      │
      │◄── Stage 2: Inference delay (Recv TS → Detection TS)
      │    YOLO model inference on COCO + fire models (local or remote)
      ▼
[Detection results correlated]
      │
      │◄── Stage 3: Correlation & dispatch delay (Detection TS → Alert Send TS)
      │    Queue lookup, severity classification, Telegram payload build
      ▼
[Alert Sent]
```

### 10.1 Stage Delay Table — Average

| Stage | Scenario A | Scenario B1 | Scenario B2 |
|-------|-----------|------------|------------|
| **Stage 1**: Event → Recv *(transmission)* | 0.271 s | 0.233 s | 0.225 s |
| **Stage 2**: Recv → Detection *(inference)* | **0.135 s** | 1.039 s | 1.240 s |
| **Stage 3**: Detection → Alert Send *(dispatch)* | 0.072 s | 0.106 s | 0.093 s |
| **Queue Age** *(image wait in correlation queue)* | 0.478 s | 1.775 s | 2.312 s |
| **Total E2E**: Event → Alert Send | **0.478 s** | 1.775 s | 2.312 s |

### 10.2 Full Percentile Table (all stages)

| Stage | Metric | Scenario A | Scenario B1 | Scenario B2 |
|-------|--------|-----------|------------|------------|
| **Stage 1** (transmission) | avg | 0.271 s | 0.233 s | 0.225 s |
| | min | 0.036 s | 0.070 s | 0.062 s |
| | max | 2.105 s | 1.924 s | 3.277 s |
| | p50 | 0.164 s | 0.118 s | 0.116 s |
| | p95 | 1.036 s | 1.754 s | 1.128 s |
| **Stage 2** (inference) | avg | **0.135 s** | 1.039 s | 1.240 s |
| | min | −1.323 s* | −1.151 s* | −0.571 s* |
| | max | 1.163 s | 2.425 s | 2.090 s |
| | p50 | 0.124 s | 1.048 s | 1.537 s |
| | p95 | 0.864 s | 2.390 s | 2.090 s |
| **Stage 3** (dispatch) | avg | 0.072 s | 0.106 s | 0.093 s |
| | min | 0.001 s | −0.001 s* | 0.002 s |
| | max | 1.330 s | 1.168 s | 0.584 s |
| | p50 | 0.013 s | 0.027 s | 0.038 s |
| | p95 | 0.625 s | 1.035 s | 0.584 s |
| **Total E2E** | avg | **0.478 s** | 1.775 s | 2.312 s |
| | min | 0.055 s | 0.570 s | 0.850 s |
| | max | 2.116 s | 2.985 s | 4.336 s |
| | p50 | 0.317 s | 1.878 s | 2.315 s |
| | p95 | 1.375 s | 2.835 s | 3.301 s |

> \* Negative values in Stage 2 min are caused by NTP clock drift between nodes (up to ~1.3 s). They are real clock skew artefacts — see §5.

### 10.3 Stage-by-Stage Observations

**Stage 1 — Transmission (Event → Recv)**
- Nearly **constant across scenarios** (~0.225–0.271 s avg), confirming the network/ZeroMQ layer is not affected by local compute load.
- The slight decrease in B1/B2 is because the motion source is now local (pi3-motion) rather than crossing a physical hop to pi5.
- Spikes to 2–3 s max are caused by TCP buffer backpressure when pi3 is CPU-saturated.

**Stage 2 — Inference (Recv → Detection)**
- This is the **dominant bottleneck** in B1 and B2.
- Scenario A: **0.135 s avg** — detection runs on dedicated pi4, fast and uncontested.
- Scenario B1: **1.039 s avg (7.7× slower)** — pi3 runs COCO + fire inference while also doing alert correlation + forwarding.
- Scenario B2: **1.240 s avg (9.2× slower)** — pi3 runs motion + detection models together.
- p95 in B1 reaches 2.39 s — meaning 1 in 20 frames waits over 2 seconds just for inference.

**Stage 3 — Dispatch (Detection → Alert Send)**
- Consistently low across all scenarios: **0.072–0.106 s avg**.
- Maximum spikes (1.33 s in A, 1.17 s in B1) are rare and correlate with Telegram API response time, not local processing.
- This stage is not a bottleneck under any scenario tested.

**Between-Stage Dominance (Scenario A)**:
```
Stage 1: 56.7% of E2E  (transmission)
Stage 2: 28.2% of E2E  (inference)
Stage 3: 15.1% of E2E  (dispatch)
```

**Between-Stage Dominance (Scenario B1)**:
```
Stage 1: 13.1% of E2E  (transmission)
Stage 2: 58.5% of E2E  (inference)  ← bottleneck
Stage 3:  5.9% of E2E  (dispatch)
Queue wait: 22.5%       (pi3 coordinator backlog — not captured in stage logs)
```

**Between-Stage Dominance (Scenario B2)**:
```
Stage 1:  9.7% of E2E  (transmission)
Stage 2: 53.6% of E2E  (inference)  ← bottleneck
Stage 3:  4.0% of E2E  (dispatch)
Queue wait: 32.7%       (pi3 coordinator backlog — not captured in stage logs)
```

> Queue wait = additional time an image spends sitting in the alert coordinator's pending-events dict before results arrive, beyond the directly measured stage latencies. It grows monotonically from 0% (Scenario A) to 22.5% (B1) to 32.7% (B2), driven by pi3 CPU saturation.

---

## 11. Comparison Charts

> Charts are saved in `logs/charts/`. All images reference paths relative to this file.

### Chart 1 — Average Per-Stage Stacked Delay

![Stacked Stage Delay](charts/01_stacked_stage_delay.png)

*Each bar shows the decomposed average pipeline latency. Stage 2 (inference, orange) grows 9× from Scenario A to B2.*

---

### Chart 2 — Per-Stage Grouped Comparison (avg + min/max whiskers + p95 ◆)

![Grouped Stage Comparison](charts/02_grouped_stage_comparison.png)

*Grouped bars for all stages and E2E. Error whiskers show min–max range. Diamond markers show p95. Stage 2 variance explodes in B1/B2.*

---

### Chart 3 — E2E Latency Percentile Profile

![E2E Percentile Profile](charts/03_e2e_percentile_profile.png)

*Min, p50, avg, p95, and max E2E latency by scenario. Scenario A dominates on every percentile.*

---

### Chart 4 — Per-Stage Subplots (avg ± min/max)

![Per Stage Subplots](charts/04_per_stage_subplots.png)

*Each stage shown individually. Stage 1 is flat (network, unaffected by load). Stage 2 reveals load-driven degradation. Stage 3 is consistently negligible.*

---

### Chart 5 — Node Resource Heatmap

![Resource Heatmap](charts/05_resource_heatmap.png)

*CPU %, Memory %, and Temperature heatmap for each node in each scenario. pi3 in B1 is clearly the hotspot.*

---
### Chart 6 — All 9 Resource Metrics per Node, Grouped Bar (3×3 Grid)

![Grouped Resource per Node](charts/06_grouped_resource_per_node.png)

*3×3 grid of grouped bar subplots — one per metric, bars grouped by node (pi3=red, pi4=blue, pi5=green). Nodes absent from a scenario have no bar.*

| Row | Col 1 | Col 2 | Col 3 |
|-----|-------|-------|-------|
| 1 | CPU Avg % | CPU Peak % | Memory Avg % |
| 2 | Temp Avg °C | Temp Peak °C | Disk Read KB/s |
| 3 | Disk Write KB/s | Net Upload KB/s | Net Download KB/s |

Key highlights visible in the chart:
- **CPU Avg/Peak**: pi3 jumps from 3.8%/53.3% (A) to 72.6%/95.1% (B1) — near saturation
- **Memory**: pi3 climbs from 35.9% (A) to 68.9% (B1) — minimal OOM headroom
- **Temp Peak**: pi4 reaches 70.1°C in B2 — on the Raspberry Pi thermal throttle boundary
- **Disk Write**: pi3-B2 spikes to 2,733 KB/s vs 18 KB/s in A — model swapping under memory pressure
- **Network**: flat ~0.1 KB/s across all nodes/scenarios — never a bottleneck

---
*Analysis scripts: `_stage_delay.py`, `_gen_charts.py`, `_analyze.py`, `_analyze_htop.py` (auto-generated, safe to delete)*
