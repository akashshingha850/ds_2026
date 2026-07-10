# TODO — Roadmap & Future Work

> **Vision:** evolve the current 3-node surveillance demo into a **scalable, decentralized,
> fault-tolerant edge platform** where a business can **plug in another Raspberry Pi (or any
> edge box) and instantly add capacity or a new capability** — detection, analytics, big-data
> processing, storage — with load balancing and failover handled automatically.

The system today ([README.md](README.md)) already proves the core loop: a SIYI A8 Mini camera →
`motion` → `detection_coco` / `detection_fire` → `alert`, over **ROS 2 Humble / CycloneDDS**, on a
**Docker Swarm** of Raspberry Pis, with a `system_monitor`, a `rebalancer`, and a Swarm dashboard.
This document is the backlog to turn that demo into a product.

---

## 0. Where we are vs. where we're going

| Capability | Today | Target |
|---|---|---|
| Scaling | Manual `docker swarm join` + redeploy | **Zero-touch:** flash a Pi, it auto-joins and advertises its capabilities |
| Service placement | Naive `rebalancer.sh` (moves a service only when one node is idle *and* another has >1) | **Load- & thermal-aware** scheduler driven by `system_monitor` telemetry |
| Detection scaling | 1 replica per detector, pinned per host | **Work-queue** with N competing consumers, autoscaled by backlog |
| Fault tolerance | `restart_policy: any`; `alert` is a single replica (SPOF) | Replicated coordinator, durable queue, health-checked failover |
| Services offered | motion, detection, alert, monitor | + **storage, analytics, big-data, API, notifications, OTA** |
| Users | Single hardcoded camera, no UI | **Multi-tenant, multi-camera, web console, billing** |

### Known limitations driving the priorities (from our own benchmarks in [README.md](README.md))

- **Per-host coupling:** topics are namespaced per device in [shared/ros_common.py](shared/ros_common.py),
  so `motion`+`detection`+`alert` must land on the **same node** to talk. This blocks true horizontal
  scaling of detection — the single biggest architectural blocker. **→ §1, §2.**
- **Detection rate collapses 54.5% → 8.3%** as nodes are removed: images expire from the alert
  correlation queue (up to **108 orphan events**) under inference backpressure. **→ §3.**
- **Compute-bound & thermal-bound:** `pi3` saturates at 72–95% CPU when co-located; `pi4` hits
  **70.1 °C** (throttle threshold). The rebalancer ignores both CPU and temperature. **→ §2.**
- **`alert` is a single point of failure** and holds all in-flight correlation state in memory. **→ §3.**

---

## 1. Platform & orchestration — make "add a unit" real

- [ ] **Zero-touch node onboarding.** Pre-baked Pi image that on first boot fetches the Swarm
      join-token from a bootstrap/manager service and joins automatically (no SSH). Consider
      `docker swarm join-token` served over a provisioning endpoint, or a QR-code activation flow.
- [ ] **Capability-based node labels.** Tag nodes on join (`gpu=coral|hailo|none`, `role=storage`,
      `arch`, `thermal_class`) so services schedule onto *capable* hardware instead of hostname
      constraints hardcoded in [docker-compose.yml](docker-compose.yml) (`node.hostname != pi3`).
- [ ] **Service discovery / registry.** Replace per-host DDS namespacing (`shared/ros_common.py`)
      with a **shared namespace or work-queue** so any `detection` worker on any node can serve any
      `motion` source. Decoupling this is the prerequisite for elastic scaling (§2).
- [ ] **Evaluate K3s / MicroK8s** as an alternative to Swarm for richer scheduling, HPA-style
      autoscaling, and CRDs — keep Swarm as the "lite" tier for tiny fleets.
- [ ] **Declarative fleet spec.** One file describing "this tenant wants 2 detectors, 1 storage,
      1 analytics" that the platform reconciles onto available units.

## 2. Load balancing & autoscaling

- [ ] **Telemetry-driven scheduler.** Feed `system_monitor` CPU/RAM/**temperature** into placement
      decisions; retire or augment the idle-node heuristic in [rebalancer/rebalancer.sh](rebalancer/rebalancer.sh).
- [ ] **Work-queue detection (competing consumers).** `motion` publishes frames to a shared queue;
      any number of `detection` workers pull, infer, and return results keyed by `image_id`. Natural
      load balancing + linear scale-out. (Redis Streams / NATS JetStream / MQTT / ROS 2 actions.)
- [ ] **Backlog-based autoscaling.** Scale `detection` replicas up when queue depth / motion rate
      grows, down when idle — the mechanism that lets a customer "add units for more throughput."
- [ ] **Thermal-aware placement.** Avoid the measured 70 °C throttle; drain work from hot nodes.
- [ ] **Inference routing / tiering.** Send heavy frames (or heavy models) to accelerator nodes
      (Coral TPU, Hailo-8, or a GPU box); keep light work on bare Pis.
- [ ] **Batching** of frames per inference call to raise detector throughput under load.

## 3. Fault tolerance & reliability

- [ ] **Durable, replayable message buffer.** Persist motion frames + detections so they survive a
      slow/absent detector instead of expiring from the in-memory correlation window (root cause of
      the orphan-event spikes). Adds at-least-once delivery + backpressure.
- [ ] **Replicate the `alert` coordinator.** Remove the SPOF: leader-elected or sharded-by-`image_id`
      correlation with shared state (Redis / Raft), so an alert-node failure doesn't drop events.
- [ ] **Re-enable health checks.** The healthcheck block is commented out in
      [docker-compose.yml](docker-compose.yml); add real liveness/readiness probes per service so
      Swarm restarts/reschedules on hang, not just on crash.
- [ ] **Graceful degradation policy.** Explicit rules for node loss (e.g. drop `fire` model before
      `coco`, shed FPS) instead of implicit collapse.
- [ ] **Data replication with eventual consistency** across storage nodes (§4) so recordings survive
      a single-node loss.
- [ ] **DDS partition / split-brain handling** for multi-subnet or flaky-Wi-Fi fleets.

## 4. New services / units (pluggable capabilities)

Each is a containerized microservice a customer can "turn on" by adding a unit. Several are already
sketched under [.draft/](.draft/).

- [ ] **`storage` / recording service.** Record clips + snapshots + metadata on motion/detection
      events; retention & rotation; tiered local → NAS → cloud. (See `.draft/record.py`,
      `.draft/mediamtx/`.) Listed as "Task 4" in [report/proposed_architecture.md](report/proposed_architecture.md).
- [ ] **`event-store` / database.** Replace flat per-host log files with a queryable store
      (SQLite/Postgres/TimescaleDB) for events, detections, and metrics — foundation for analytics,
      dashboards, and billing.
- [ ] **`analytics` (edge) service.** Object counting, dwell time, line-crossing, zone intrusion,
      heatmaps, hourly/daily trends. (Edge-analytics task in the proposed architecture.)
- [ ] **`big-data` / batch service.** Aggregate historical events (Spark / DuckDB / Parquet) for
      reporting, model evaluation, and long-range trends — the "batch analytics" tier.
- [ ] **`api-gateway`.** REST + gRPC + WebSocket surface for dashboards, mobile apps, and 3rd-party
      integrations; single authenticated entry point to the fleet.
- [ ] **`stream-relay`.** Re-stream live/recorded video to browser/cloud viewers (mediamtx already
      vendored in `.draft/mediamtx/`).
- [ ] **More detectors.** Weapon (drafted in `.draft/detection_weapon.py`), LPR/ANPR, face/PPE,
      people-in-restricted-zone — all drop-in via the `DETECTOR` env pattern in
      [detection/detection.py](detection/detection.py).
- [ ] **`notification` expansion.** Email, SMS, push, WhatsApp, Slack alongside the current Telegram
      path in [alert/alert.py](alert/alert.py).
- [ ] **`model-manager` / OTA.** Push new models, configs, and firmware/software updates to edge
      units safely (staged rollout, rollback). ("Remote Firmware/Software Updates" in the proposal.)

## 5. Business / startup features

- [ ] **Multi-tenant + multi-camera.** Today `MOTION_URL` is a single hardcoded RTSP source in
      [config.yaml](config.yaml). Support many cameras and tenant isolation.
- [ ] **Web admin console.** Add/remove units, assign services to units, view live alerts & health,
      manage cameras — the "add a unit for more services" UX made visible.
- [ ] **Onboarding wizard.** "Plug in a Pi, scan a QR code, it joins your fleet and offers to run
      detection/storage/analytics."
- [ ] **Users, roles, and org/tenant management.**
- [ ] **Usage metering & billing hooks.** Per unit, per detection, per stored GB, per alert — the
      commercial model for elastic edge capacity.
- [ ] **Licensing / device activation** and per-unit entitlement.
- [ ] **SLA / uptime reporting** per tenant.

## 6. Security & middleware

- [ ] **Secure the bus.** DDS traffic is open multicast today; enable **SROS 2** (auth + encryption)
      or move sensitive channels to authenticated MQTT/TLS.
- [ ] **TLS everywhere** for webhooks, the API gateway, and any ZMQ/telemetry channels.
- [ ] **Device identity & provisioning** — per-unit certificates issued at onboarding.
- [ ] **Secrets management** beyond `.env` (Vault / Docker/K8s secrets).
- [ ] **Audit logging** of admin actions and alert dispatches.

## 7. Observability

- [ ] **Prometheus + Grafana.** `node-exporter` / `cadvisor` are already stubbed (commented) in
      [docker-compose.yml](docker-compose.yml) — wire them up plus per-service metrics.
- [ ] **Centralized logs.** Ship the per-host `logs/{hostname}.log` files to Loki/ELK.
- [ ] **Distributed tracing.** We already correlate the whole pipeline by `image_id`; export those
      as spans to visualize per-stage latency (motion → transport → inference → dispatch) live,
      not just in the offline `.result/` analysis.
- [ ] **Health/thermal alerting** — alert on node saturation and throttle, not only on security events.

## 8. Edge–cloud continuum (maps to the course increments)

Aligns the roadmap with [report/guideline/project_requirement.txt](report/guideline/project_requirement.txt)
("distributed 5G IoT gateway … Edge ML/LLM … thousands of devices").

- [ ] **Optional cloud tier** for heavy ML training and batch analytics (increments 9–10).
- [ ] **Adaptive edge↔cloud scheduling:** immediate analytics at the edge, deeper insight in the
      cloud (increment 12).
- [ ] **Federated / continual learning:** edge collects hard samples, cloud retrains, pushes updated
      models back via the `model-manager` (§4) (increment 11).
- [ ] **Consensus & consistent config / OTA** across the fleet (increment 3).
- [ ] **Replication with eventual consistency** for the edge data store (increment 5).

---

## Suggested phasing

| Phase | Theme | Highlights |
|---|---|---|
| **P1 — Elastic core** | Unblock scaling | Decouple per-host namespace (§1), work-queue detection + backlog autoscaling (§2), durable buffer + health checks (§3) |
| **P2 — More services** | Breadth | `storage`, `event-store`, `analytics`, `api-gateway`, extra detectors (§4) |
| **P3 — Product** | Go-to-market | Multi-tenant, web console, onboarding wizard, metering/billing (§5), security (§6) |
| **P4 — Intelligence** | Edge–cloud | Big-data batch, federated learning, adaptive offload (§4, §8), full observability (§7) |

> Contributions: keep each new capability a **self-contained service** (own `Dockerfile`, config
> section in [config.yaml](config.yaml), and Swarm/K3s deploy block) so a customer can enable it by
> simply adding a unit.
