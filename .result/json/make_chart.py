"""
make_chart.py
-------------
Chart generator for distributed-system scenario analysis.
Each chart function accepts pre-loaded `sysmon_data` (and optionally
other data dicts) and saves:
  - charts/<name>.png
  - charts/<name>.json   ← raw data used to draw the chart

Add new chart functions at the bottom; call them in main().
"""

import json
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── paths ─────────────────────────────────────────────────────────────────────
BASE       = os.path.dirname(os.path.abspath(__file__))
CHART_DIR  = os.path.join(BASE, "charts")
os.makedirs(CHART_DIR, exist_ok=True)

# ── constants ─────────────────────────────────────────────────────────────────
SCENARIOS = {
    "A":  "scenario_A",
    "B1": "scenario_B1",
    "B2": "scenario_B2",
}

NODE_COLOURS = {
    "pi3": "#4C72B0",
    "pi4": "#DD8452",
    "pi5": "#55A868",
}

# ── data loaders ──────────────────────────────────────────────────────────────
def load_alert() -> dict:
    """Return { scenario_label → { key → {avg, max} } } for pipeline stages."""
    import statistics

    def _stats(vals):
        clean = [v for v in vals if v is not None and -2 < v < 60]
        if not clean:
            return {"avg": None, "max": None}
        return {"avg": round(statistics.mean(clean), 4),
                "max": round(max(clean), 4)}

    result = {}
    for label, folder in SCENARIOS.items():
        scen_dir = os.path.join(BASE, folder)
        comm_vals, inf_vals, disp_vals, e2e_vals = [], [], [], []

        # --- communication + inference: from detection JSON files ---
        for fname in os.listdir(scen_dir):
            if "detection" not in fname or not fname.endswith(".json"):
                continue
            with open(os.path.join(scen_dir, fname)) as f:
                doc = json.load(f)
            for ev in doc["events"].get("detections", []):
                comm_vals.append(ev.get("queue_age_s"))
                dec  = ev.get("decode_ms", 0) or 0
                inf  = ev.get("inference_ms", 0) or 0
                inf_vals.append((dec + inf) / 1000.0)

        # --- dispatch + e2e: from alert JSON ---
        alert_path = os.path.join(scen_dir, "pi3_alert.json")
        if os.path.exists(alert_path):
            with open(alert_path) as f:
                doc = json.load(f)
            for ev in doc["events"].get("image_received", []):
                lat = ev.get("latency", {})
                disp_vals.append(lat.get("dispatch_s"))
                e2e_vals.append(lat.get("e2e_recv_to_alert_s"))

        result[label] = {
            "comm":     _stats(comm_vals),
            "inference": _stats(inf_vals),
            "dispatch": _stats(disp_vals),
            "e2e":      _stats(e2e_vals),
        }
    return result


def load_sysmon() -> dict:
    """Return { scenario_label → { node → summary_dict } }."""
    data = {}
    for label, folder in SCENARIOS.items():
        data[label] = {}
        scen_dir = os.path.join(BASE, folder)
        for fname in sorted(os.listdir(scen_dir)):
            if not fname.endswith("_sysmon.json"):
                continue
            node = fname.replace("_sysmon.json", "")
            with open(os.path.join(scen_dir, fname)) as f:
                doc = json.load(f)
            data[label][node] = doc["summary"]
    return data


def save_chart(fig: plt.Figure, name: str, chart_data: dict) -> None:
    """Save figure as PNG and its source data as JSON into charts/."""
    png_path  = os.path.join(CHART_DIR, f"{name}.png")
    json_path = os.path.join(CHART_DIR, f"{name}.json")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    with open(json_path, "w") as f:
        json.dump(chart_data, f, indent=2)
    print(f"  Saved: charts/{name}.png")
    print(f"  Saved: charts/{name}.json")


# ── helper: draw one grouped-bar subplot ──────────────────────────────────────
def draw_grouped_bars(ax, scen_labels, node_data, metric_key, stat,
                      ylim, bar_w=0.22, group_pad=0.15):
    """
    Draw clustered bars on `ax`.
    node_data: { scen → { node → summary_dict } }
    Returns list of record dicts for JSON export.
    """
    records = []
    xtick_centers, xtick_labels = [], []
    x_cursor = 0.0

    for scen in scen_labels:
        nodes = sorted(node_data[scen].keys())
        n     = len(nodes)
        offsets = np.linspace(-(n - 1) / 2 * bar_w, (n - 1) / 2 * bar_w, n)
        xtick_centers.append(x_cursor + (n - 1) / 2 * bar_w)
        xtick_labels.append(f"Scenario {scen}")

        for node, offset in zip(nodes, offsets):
            val = (node_data[scen][node].get(metric_key) or {}).get(stat, 0.0)
            color = NODE_COLOURS.get(node, "#888888")
            ax.bar(x_cursor + offset, val,
                   width=bar_w * 0.9, color=color,
                   edgecolor="white", linewidth=0.6, zorder=3)
            ax.text(x_cursor + offset, val + (ylim[1] - ylim[0]) * 0.012,
                    f"{val:.1f}", ha="center", va="bottom",
                    fontsize=7.5, color="#333333")
            records.append({"scenario": scen, "node": node,
                            "metric": metric_key, "stat": stat, "value": val})

        x_cursor += n * bar_w + group_pad

    ax.set_xticks(xtick_centers)
    ax.set_xticklabels(xtick_labels, fontsize=9)
    ax.set_ylim(ylim)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    return records


# ── chart 01: 2×3 resource avg/peak ──────────────────────────────────────────
def chart_resource_avg_peak(sysmon_data: dict) -> None:
    """
    2 rows × 3 cols grouped bar chart.
      Rows : Average | Peak
      Cols : CPU %  | RAM %  | Temp °C
    Legend at top-right; one-line title.
    """
    METRICS = [
        ("cpu_pct", "CPU Usage",   "%",  (0, 110)),
        ("mem_pct", "RAM Usage",   "%",  (0, 110)),
        ("temp_c",  "Temperature", "°C", (30, 90)),
    ]
    ROWS = [("avg", "Average"), ("max", "Peak")]

    scen_labels = list(SCENARIOS.keys())
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))

    fig.suptitle("CPU / RAM / Temperature — Average vs Peak per Node and Scenario",
                 fontsize=13, fontweight="bold")

    # legend top-right inside figure
    legend_handles = [mpatches.Patch(color=c, label=n)
                      for n, c in NODE_COLOURS.items()]
    fig.legend(handles=legend_handles, title="Node",
               loc="upper right", fontsize=9, title_fontsize=9,
               frameon=True, bbox_to_anchor=(1.0, 1.0))

    all_records = []

    for row_idx, (stat, row_label) in enumerate(ROWS):
        for col_idx, (metric_key, metric_label, unit, ylim) in enumerate(METRICS):
            ax = axes[row_idx, col_idx]
            records = draw_grouped_bars(ax, scen_labels, sysmon_data,
                                        metric_key, stat, ylim)
            all_records.extend(records)
            ax.set_title(f"{metric_label} ({unit}) — {row_label}",
                         fontsize=10, fontweight="bold")
            ax.set_ylabel(f"{metric_label} ({unit})", fontsize=8)

    plt.tight_layout()
    chart_data = {
        "chart": "resource_avg_peak",
        "description": "2x3 grouped bar: rows=Average/Peak, cols=CPU/RAM/Temp",
        "rows": [r for _, r in ROWS],
        "cols": [m for m, *_ in METRICS],
        "data": all_records,
    }
    save_chart(fig, "01_resource_avg_peak", chart_data)
    plt.close(fig)


# ── chart 02: stage delay stacked bar (2 rows × 1 col) ───────────────────────
def chart_stage_delay(alert_data: dict) -> None:
    """2×1 stacked bar: Avg/Peak rows, Scenario bars, Comm/Inference/Dispatch segments."""
    STAGES = [
        ("comm",      "Communication", "#4C72B0"),
        ("inference", "Inference",     "#DD8452"),
        ("dispatch",  "Dispatch",      "#55A868"),
    ]
    scen_labels = list(SCENARIOS.keys())
    ROWS = [("avg", "Average Delay (s)"), ("max", "Peak Delay (s)")]
    BAR_W = 0.45

    fig, axes = plt.subplots(2, 1, figsize=(8, 10), sharex=False)
    fig.suptitle("Pipeline Stage Delay per Scenario — Average vs Peak (Stacked)",
                 fontsize=13, fontweight="bold")

    legend_handles = [mpatches.Patch(color=c, label=lbl) for _, lbl, c in STAGES]
    fig.legend(handles=legend_handles, title="Stage", loc="upper right",
               fontsize=9, title_fontsize=9, frameon=True, bbox_to_anchor=(1.0, 1.0))

    all_records = []
    x_pos = np.arange(len(scen_labels))

    for row_idx, (stat, row_label) in enumerate(ROWS):
        ax = axes[row_idx]
        bottoms = np.zeros(len(scen_labels))
        for stage_key, stage_lbl, color in STAGES:
            vals = np.array([
                (alert_data[scen].get(stage_key) or {}).get(stat) or 0.0
                for scen in scen_labels
            ])
            ax.bar(x_pos, vals, BAR_W, bottom=bottoms, color=color,
                   edgecolor="white", linewidth=0.8, zorder=3)
            for xi, (val, bot) in enumerate(zip(vals, bottoms)):
                if val > 0.05:
                    ax.text(xi, bot + val / 2, f"{val:.2f}",
                            ha="center", va="center",
                            fontsize=8, color="white", fontweight="bold")
            for scen, val in zip(scen_labels, vals):
                all_records.append({"stat": stat, "stage": stage_key,
                                    "scenario": scen, "value_s": round(float(val), 4)})
            bottoms += vals
        for xi, (scen, total) in enumerate(zip(scen_labels, bottoms)):
            e2e = (alert_data[scen].get("e2e") or {}).get(stat)
            label = f"E2E: {e2e:.2f}s" if e2e else f"sum: {total:.2f}s"
            ax.text(xi, total + 0.02, label, ha="center", va="bottom",
                    fontsize=8, color="#333333", fontweight="bold")
        ylim_top = max(bottoms) * 1.25 + 0.3
        ax.set_ylim(0, ylim_top)
        ax.set_title(row_label, fontsize=10, fontweight="bold")
        ax.set_xticks(x_pos)
        ax.set_xticklabels([f"Scenario {s}" for s in scen_labels], fontsize=10)
        ax.set_ylabel("Delay (s)", fontsize=9)
        ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    save_chart(fig, "02_stage_delay", {
        "chart": "stage_delay_stacked",
        "description": "2x1 stacked bar: rows=Avg/Peak, bars=scenario, segments=stages",
        "stages": [s for s, *_ in STAGES],
        "scenarios": scen_labels,
        "data": all_records,
    })
    plt.close(fig)


# ── chart 03: gantt-style pipeline stage latency ─────────────────────────────
def load_gantt() -> list:
    import statistics
    def _avg(vals):
        clean = [v for v in vals if v is not None and v >= 0]
        return round(statistics.mean(clean), 4) if clean else 0.0

    rows = []
    for scen_label, folder in SCENARIOS.items():
        scen_dir = os.path.join(BASE, folder)
        dispatch_vals = []
        alert_path = os.path.join(scen_dir, "pi3_alert.json")
        if os.path.exists(alert_path):
            with open(alert_path) as f:
                doc = json.load(f)
            for ev in doc["events"].get("image_received", []):
                d = (ev.get("latency") or {}).get("dispatch_s")
                if d is not None and 0 <= d < 10:
                    dispatch_vals.append(d)
        dispatch_avg = _avg(dispatch_vals)
        for fname in sorted(os.listdir(scen_dir)):
            if "detection" not in fname or not fname.endswith(".json"):
                continue
            svc_label = fname.replace(".json", "").split("_", 1)[1]
            with open(os.path.join(scen_dir, fname)) as f:
                doc = json.load(f)
            evts = doc["events"].get("detections", [])
            if not evts:
                continue
            rows.append({
                "label":      f"Scenario {scen_label} / {svc_label.replace('_', ' ')}",
                "scenario":   scen_label, "service": svc_label,
                "comm_s":     _avg([e.get("queue_age_s", 0) or 0 for e in evts]),
                "decode_s":   _avg([(e.get("decode_ms") or 0) / 1000.0 for e in evts]),
                "infer_s":    _avg([(e.get("inference_ms") or 0) / 1000.0 for e in evts]),
                "dispatch_s": dispatch_avg,
            })
    return rows


def chart_stage_gantt(gantt_rows: list) -> None:
    """Horizontal stacked Gantt: rows=scenario/service, segments=pipeline stages."""
    SEGMENT_DEFS = [
        ("comm_s",     "Communication", "#4C72B0"),
        ("decode_s",   "Decode",        "#55A868"),
        ("infer_s",    "Inference",     "#DD8452"),
        ("dispatch_s", "Dispatch",      "#8E6BBF"),
    ]
    y_labels = [r["label"] for r in gantt_rows]
    y_pos    = np.arange(len(y_labels))
    BAR_H    = 0.55

    fig, ax = plt.subplots(figsize=(13, max(5, len(y_labels) * 1.2 + 2.0)))
    fig.suptitle("Pipeline Stage Latency — Average Time per Stage (Gantt View)",
                 fontsize=13, fontweight="bold")

    lefts = np.zeros(len(gantt_rows))
    all_records = []
    for seg_key, seg_label, color in SEGMENT_DEFS:
        vals = np.array([r[seg_key] for r in gantt_rows])
        ax.barh(y_pos, vals, BAR_H, left=lefts, color=color,
                edgecolor="white", linewidth=0.8, label=seg_label, zorder=3)
        for yi, (val, left) in enumerate(zip(vals, lefts)):
            if val > 0.04:
                ax.text(left + val / 2, yi, f"{val:.2f}s",
                        ha="center", va="center", fontsize=8,
                        color="white", fontweight="bold")
        for row, val in zip(gantt_rows, vals):
            all_records.append({"label": row["label"], "stage": seg_key,
                                 "value_s": round(float(val), 4)})
        lefts += vals
    for yi, (row, total) in enumerate(zip(gantt_rows, lefts)):
        ax.text(total + max(lefts) * 0.01, yi, f"  {total:.2f}s",
                ha="left", va="center", fontsize=8.5,
                color="#222222", fontweight="bold")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(y_labels, fontsize=9)
    ax.set_xlabel("Cumulative Latency (seconds)", fontsize=10)
    ax.set_xlim(0, max(lefts) * 1.22)
    ax.xaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.invert_yaxis()
    ax.legend(title="Stage", loc="lower right", fontsize=9, frameon=True)
    plt.tight_layout()
    save_chart(fig, "03_stage_gantt", {
        "chart": "stage_gantt",
        "description": "Horizontal stacked Gantt: rows=scenario/service, segments=pipeline stages",
        "segments": [s for s, *_ in SEGMENT_DEFS],
        "data": all_records, "rows": gantt_rows,
    })
    plt.close(fig)


# ── data loaders for new charts ───────────────────────────────────────────────
def load_alert_events() -> dict:
    """Return { scenario → list of {elapsed_s, queue_age_s, e2e_s} } from alert JSON."""
    from datetime import datetime
    result = {}
    for label, folder in SCENARIOS.items():
        path = os.path.join(BASE, folder, "pi3_alert.json")
        if not os.path.exists(path):
            result[label] = []
            continue
        with open(path) as f:
            doc = json.load(f)
        evts = doc["events"].get("image_received", [])
        rows = []
        t0 = None
        for ev in evts:
            recv_s = ev.get("recv_ts")
            if not recv_s or recv_s == "None":
                continue
            try:
                t = datetime.fromisoformat(recv_s)
            except Exception:
                continue
            if t0 is None:
                t0 = t
            elapsed = (t - t0).total_seconds()
            qa  = ev.get("queue_age_s")
            lat = ev.get("latency") or {}
            e2e = lat.get("e2e_recv_to_alert_s")
            rows.append({
                "elapsed_s":   round(elapsed, 2),
                "queue_age_s": qa,
                "e2e_s":       e2e,
                "image_id":    ev.get("image_id"),
            })
        result[label] = rows
    return result


def load_sysmon_samples() -> dict:
    """Return { scenario → { node → list of {elapsed_s, cpu_pct, mem_pct, temp_c} } }."""
    from datetime import datetime
    result = {}
    for label, folder in SCENARIOS.items():
        result[label] = {}
        scen_dir = os.path.join(BASE, folder)
        for fname in sorted(os.listdir(scen_dir)):
            if not fname.endswith("_sysmon.json"):
                continue
            node = fname.replace("_sysmon.json", "")
            with open(os.path.join(scen_dir, fname)) as f:
                doc = json.load(f)
            samples = doc.get("samples", [])
            t0 = None
            rows = []
            for s in samples:
                ts = s.get("ts")
                if not ts:
                    continue
                try:
                    t = datetime.fromisoformat(ts)
                except Exception:
                    continue
                if t0 is None:
                    t0 = t
                rows.append({
                    "elapsed_s": round((t - t0).total_seconds(), 1),
                    "cpu_pct":   s.get("cpu_pct"),
                    "mem_pct":   s.get("mem_pct"),
                    "temp_c":    s.get("temp_c"),
                })
            result[label][node] = rows
    return result


def load_detection_dist() -> dict:
    """Return { scenario → { service → {inference_ms: [...], decode_ms: [...]} } }."""
    result = {}
    for label, folder in SCENARIOS.items():
        result[label] = {}
        scen_dir = os.path.join(BASE, folder)
        for fname in sorted(os.listdir(scen_dir)):
            if "detection" not in fname or not fname.endswith(".json"):
                continue
            svc = fname.replace(".json", "").split("_", 1)[1]  # detection_coco / detection_fire
            with open(os.path.join(scen_dir, fname)) as f:
                doc = json.load(f)
            evts = doc["events"].get("detections", [])
            result[label][svc] = {
                "inference_ms": [e["inference_ms"] for e in evts if e.get("inference_ms")],
                "decode_ms":    [e["decode_ms"]    for e in evts if e.get("decode_ms")],
            }
    return result


def load_alert_pipeline_summary() -> dict:
    """Return { scenario → alert summary dict } from alert JSON files."""
    result = {}
    for label, folder in SCENARIOS.items():
        path = os.path.join(BASE, folder, "pi3_alert.json")
        if not os.path.exists(path):
            result[label] = {}
            continue
        with open(path) as f:
            doc = json.load(f)
        result[label] = doc.get("summary", {})
    return result


def load_assembly_breakdown() -> dict:
    """Count full vs partial assemblies; partial = detection_ts is None/missing."""
    result = {}
    for label, folder in SCENARIOS.items():
        path = os.path.join(BASE, folder, "pi3_alert.json")
        if not os.path.exists(path):
            result[label] = {"full": 0, "partial": 0}
            continue
        with open(path) as f:
            doc = json.load(f)
        full, partial = 0, 0
        for ev in doc["events"].get("image_received", []):
            dts = ev.get("detection_ts")
            if dts and dts != "None":
                full += 1
            else:
                partial += 1
        result[label] = {"full": full, "partial": partial}
    return result


# ── chart 04: E2E latency time-series ────────────────────────────────────────
SCEN_COLOURS = {"A": "#4C72B0", "B1": "#DD8452", "B2": "#55A868"}


def chart_e2e_timeseries(alert_events: dict) -> None:
    """Line chart: queue_age_s over elapsed time, one line per scenario."""
    fig, ax = plt.subplots(figsize=(12, 5))
    fig.suptitle("End-to-End Latency (Publish → Alert) Over Elapsed Time",
                 fontsize=13, fontweight="bold")

    all_records = []
    for label, rows in alert_events.items():
        xs = [r["elapsed_s"]   for r in rows if r["queue_age_s"] is not None]
        ys = [r["queue_age_s"] for r in rows if r["queue_age_s"] is not None]
        if not xs:
            continue
        color = SCEN_COLOURS.get(label, "#888888")
        ax.plot(xs, ys, "o-", color=color, markersize=4,
                linewidth=1.4, label=f"Scenario {label}", zorder=3)
        if ys:
            mean_y = float(np.mean(ys))
            p95_y  = float(np.percentile(ys, 95))
            ax.axhline(mean_y, color=color, linewidth=0.8,
                       linestyle="--", alpha=0.6)
            ax.text(xs[-1], mean_y, f"  μ={mean_y:.2f}s",
                    va="center", fontsize=7.5, color=color)
        for r in rows:
            if r["queue_age_s"] is not None:
                all_records.append({"scenario": label,
                                    "elapsed_s": r["elapsed_s"],
                                    "queue_age_s": r["queue_age_s"]})

    ax.set_xlabel("Elapsed Time (s)", fontsize=10)
    ax.set_ylabel("Queue Age / E2E Latency (s)", fontsize=10)
    ax.legend(loc="upper right", fontsize=9, frameon=True)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    save_chart(fig, "04_e2e_timeseries", {
        "chart": "e2e_timeseries",
        "description": "queue_age_s over elapsed seconds, one line per scenario",
        "data": all_records,
    })
    plt.close(fig)


# ── chart 05: CPU & temperature time-series per node ─────────────────────────
def chart_resource_timeseries(samples: dict) -> None:
    """3 subplots (one per scenario): CPU % and Temp °C over time per node."""
    scen_labels = list(SCENARIOS.keys())
    fig, axes = plt.subplots(len(scen_labels), 1,
                             figsize=(13, 4.5 * len(scen_labels)))
    fig.suptitle("CPU Utilisation and Temperature Over Time per Node",
                 fontsize=13, fontweight="bold")

    all_records = []
    for ax_idx, label in enumerate(scen_labels):
        ax  = axes[ax_idx]
        ax2 = ax.twinx()
        node_data = samples.get(label, {})
        plotted_any = False
        for node in sorted(node_data.keys()):
            rows = node_data[node]
            if not rows:
                continue
            xs  = [r["elapsed_s"] for r in rows]
            cpu = [r["cpu_pct"]   for r in rows]
            tmp = [r["temp_c"]    for r in rows]
            color = NODE_COLOURS.get(node, "#888888")
            ax.plot(xs, cpu, color=color, linewidth=1.0,
                    alpha=0.85, label=f"{node} CPU")
            ax2.plot(xs, tmp, color=color, linewidth=1.0,
                     linestyle="--", alpha=0.5)
            plotted_any = True
            for r in rows:
                all_records.append({"scenario": label, "node": node,
                                    "elapsed_s": r["elapsed_s"],
                                    "cpu_pct": r["cpu_pct"], "temp_c": r["temp_c"]})
        ax.set_title(f"Scenario {label}", fontsize=10, fontweight="bold")
        ax.set_ylabel("CPU %", fontsize=9)
        ax2.set_ylabel("Temp °C", fontsize=9, color="#888888")
        ax.set_ylim(0, 105)
        ax.set_xlabel("Elapsed Time (s)", fontsize=9)
        ax.yaxis.grid(True, linestyle="--", alpha=0.3, zorder=0)
        ax.set_axisbelow(True)
        ax.spines[["top"]].set_visible(False)
        if plotted_any:
            ax.legend(loc="upper right", fontsize=8, frameon=True,
                      title="— CPU  -- Temp")

    plt.tight_layout()
    save_chart(fig, "05_resource_timeseries", {
        "chart": "resource_timeseries",
        "description": "CPU% and Temp°C over time per node, one subplot per scenario",
        "data": all_records,
    })
    plt.close(fig)


# ── chart 06: alert pipeline stage counts grouped bar ────────────────────────
def chart_alert_pipeline(pipeline_data: dict) -> None:
    """Grouped bar: alert pipeline metrics per scenario."""
    METRICS = [
        ("images_received",         "Images Received",     "#4C72B0"),
        ("images_with_detections",  "With Detections",     "#55A868"),
        ("orphan_events",           "Orphan Events",       "#DD8452"),
        ("alerts_sent",             "Alerts Dispatched",   "#8E6BBF"),
        ("telegram_acks",           "Telegram ACKs",       "#C44E52"),
    ]
    scen_labels = list(SCENARIOS.keys())
    BAR_W = 0.14
    x_pos = np.arange(len(METRICS))

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle("Alert Pipeline Stage Counts per Scenario",
                 fontsize=13, fontweight="bold")

    offsets = np.linspace(-(len(scen_labels)-1)/2*BAR_W,
                           (len(scen_labels)-1)/2*BAR_W,
                           len(scen_labels))
    all_records = []
    for scen, offset in zip(scen_labels, offsets):
        summary = pipeline_data.get(scen, {})
        vals = [summary.get(mk, 0) or 0 for mk, *_ in METRICS]
        color = SCEN_COLOURS.get(scen, "#888")
        bars = ax.bar(x_pos + offset, vals, BAR_W * 0.9,
                      color=color, edgecolor="white",
                      linewidth=0.6, label=f"Scenario {scen}", zorder=3)
        for xi, val in enumerate(vals):
            if val > 0:
                ax.text(xi + offset, val + 0.5, str(int(val)),
                        ha="center", va="bottom", fontsize=7.5, color="#333")
        for mk, val in zip([m for m, *_ in METRICS], vals):
            all_records.append({"scenario": scen, "metric": mk, "value": val})

    ax.set_xticks(x_pos)
    ax.set_xticklabels([lbl for _, lbl, _ in METRICS], fontsize=9)
    ax.set_ylabel("Count", fontsize=10)
    ax.set_ylim(0, max(
        [pipeline_data.get(s, {}).get(mk, 0) or 0
         for s in scen_labels for mk, *_ in METRICS], default=1
    ) * 1.3)
    ax.legend(loc="upper right", fontsize=9, frameon=True)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    save_chart(fig, "06_alert_pipeline", {
        "chart": "alert_pipeline_counts",
        "description": "Grouped bar: alert pipeline counts per scenario",
        "metrics": [m for m, *_ in METRICS],
        "data": all_records,
    })
    plt.close(fig)


# ── chart 07: empirical CDF of E2E latency ───────────────────────────────────
def chart_latency_cdf(alert_events: dict) -> None:
    """Empirical CDF of queue_age_s per scenario."""
    fig, ax = plt.subplots(figsize=(9, 5))
    fig.suptitle("Empirical CDF of End-to-End Latency (Publish → Alert Recv)",
                 fontsize=13, fontweight="bold")

    all_records = []
    for label, rows in alert_events.items():
        vals = sorted([r["queue_age_s"] for r in rows
                       if r["queue_age_s"] is not None and r["queue_age_s"] >= 0])
        if not vals:
            continue
        n    = len(vals)
        cdf  = np.arange(1, n + 1) / n
        color = SCEN_COLOURS.get(label, "#888")
        ax.step(vals, cdf, where="post", color=color,
                linewidth=2.0, label=f"Scenario {label}")
        for pct, pname in [(50, "P50"), (95, "P95")]:
            pval = float(np.percentile(vals, pct))
            pidx = np.searchsorted(vals, pval, side="right") / n
            ax.axvline(pval, color=color, linewidth=0.8, linestyle=":")
            ax.text(pval, pidx + 0.03, f"{pname}={pval:.2f}s",
                    color=color, fontsize=7.5, ha="center")
        for v, c in zip(vals, cdf):
            all_records.append({"scenario": label, "value_s": round(v, 4), "cdf": round(float(c), 4)})

    ax.set_xlabel("Queue Age / E2E Latency (s)", fontsize=10)
    ax.set_ylabel("Cumulative Probability", fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="lower right", fontsize=9, frameon=True)
    ax.xaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    save_chart(fig, "07_latency_cdf", {
        "chart": "latency_cdf",
        "description": "Empirical CDF of queue_age_s per scenario",
        "data": all_records,
    })
    plt.close(fig)


# ── chart 08: inference latency box plot ─────────────────────────────────────
def chart_inference_boxplot(det_dist: dict) -> None:
    """Box plot of inference_ms per (scenario × service)."""
    scen_labels = list(SCENARIOS.keys())
    services    = ["detection_coco", "detection_fire"]
    svc_labels  = {"detection_coco": "COCO", "detection_fire": "Fire"}
    SVC_COLOURS = {"detection_coco": "#4C72B0", "detection_fire": "#DD8452"}

    fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharey=False)
    fig.suptitle("Inference Latency Distribution per Scenario and Model",
                 fontsize=13, fontweight="bold")

    all_records = []
    for col, svc in enumerate(services):
        ax = axes[col]
        data_by_scen = []
        tick_labels  = []
        for scen in scen_labels:
            vals = (det_dist.get(scen, {}).get(svc) or {}).get("inference_ms", [])
            data_by_scen.append(vals)
            tick_labels.append(f"Scenario {scen}")
            for v in vals:
                all_records.append({"scenario": scen, "service": svc,
                                    "inference_ms": v})
        bp = ax.boxplot(data_by_scen, patch_artist=True,
                        medianprops={"color": "white", "linewidth": 2},
                        whiskerprops={"linewidth": 1.2},
                        capprops={"linewidth": 1.2},
                        flierprops={"marker": "o", "markersize": 3,
                                    "alpha": 0.5})
        color = SVC_COLOURS.get(svc, "#888")
        for patch in bp["boxes"]:
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        ax.set_xticks(range(1, len(scen_labels) + 1))
        ax.set_xticklabels(tick_labels, fontsize=9)
        ax.set_title(f"{svc_labels[svc]} Detector", fontsize=10, fontweight="bold")
        ax.set_ylabel("Inference Time (ms)", fontsize=9)
        ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    save_chart(fig, "08_inference_boxplot", {
        "chart": "inference_boxplot",
        "description": "Box plot of inference_ms per scenario×service",
        "services": services,
        "data": all_records,
    })
    plt.close(fig)


# ── chart 09: full vs partial assembly stacked bar ───────────────────────────
def chart_assembly_breakdown(assembly: dict) -> None:
    """Stacked bar: full vs partial (timeout) assemblies per scenario."""
    scen_labels = list(SCENARIOS.keys())
    BAR_W = 0.4
    x_pos = np.arange(len(scen_labels))

    full_vals    = [assembly[s]["full"]    for s in scen_labels]
    partial_vals = [assembly[s]["partial"] for s in scen_labels]

    fig, ax = plt.subplots(figsize=(7, 5))
    fig.suptitle("Alert Assembly Outcome — Full vs Partial (Timeout) per Scenario",
                 fontsize=13, fontweight="bold")

    b1 = ax.bar(x_pos, full_vals, BAR_W, color="#55A868",
                edgecolor="white", linewidth=0.8, label="Full Assembly", zorder=3)
    b2 = ax.bar(x_pos, partial_vals, BAR_W, bottom=full_vals,
                color="#DD8452", edgecolor="white", linewidth=0.8,
                label="Partial (Timeout)", zorder=3)

    for xi, (f, p) in enumerate(zip(full_vals, partial_vals)):
        if f > 0:
            ax.text(xi, f / 2, str(f), ha="center", va="center",
                    fontsize=10, color="white", fontweight="bold")
        if p > 0:
            ax.text(xi, f + p / 2, str(p), ha="center", va="center",
                    fontsize=10, color="white", fontweight="bold")
        total = f + p
        ax.text(xi, total + 0.5, f"n={total}", ha="center", va="bottom",
                fontsize=8.5, color="#333333")

    ax.set_xticks(x_pos)
    ax.set_xticklabels([f"Scenario {s}" for s in scen_labels], fontsize=10)
    ax.set_ylabel("Assembly Attempts", fontsize=10)
    ax.set_ylim(0, max(f + p for f, p in zip(full_vals, partial_vals)) * 1.25)
    ax.legend(loc="upper right", fontsize=9, frameon=True)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()

    all_records = [{"scenario": s, "full": assembly[s]["full"],
                    "partial": assembly[s]["partial"]} for s in scen_labels]
    save_chart(fig, "09_assembly_breakdown", {
        "chart": "assembly_breakdown",
        "description": "Stacked bar: full vs partial assemblies per scenario",
        "data": all_records,
    })
    plt.close(fig)


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("Loading data...")
    sysmon      = load_sysmon()
    alert       = load_alert()
    alert_evts  = load_alert_events()
    sys_samples = load_sysmon_samples()
    det_dist    = load_detection_dist()
    pipeline    = load_alert_pipeline_summary()
    assembly    = load_assembly_breakdown()

    print("\n[Chart 01] Resource avg/peak 2×3")
    chart_resource_avg_peak(sysmon)

    print("\n[Chart 02] Stage delay stacked bar")
    chart_stage_delay(alert)

    print("\n[Chart 03] Stage latency Gantt")
    chart_stage_gantt(load_gantt())

    print("\n[Chart 04] E2E latency time-series")
    chart_e2e_timeseries(alert_evts)

    print("\n[Chart 05] CPU & temperature time-series")
    chart_resource_timeseries(sys_samples)

    print("\n[Chart 06] Alert pipeline stage counts")
    chart_alert_pipeline(pipeline)

    print("\n[Chart 07] Latency CDF")
    chart_latency_cdf(alert_evts)

    print("\n[Chart 08] Inference latency box plot")
    chart_inference_boxplot(det_dist)

    print("\n[Chart 09] Assembly breakdown")
    chart_assembly_breakdown(assembly)

    print("\nDone. All outputs in: charts/")


if __name__ == "__main__":
    main()
