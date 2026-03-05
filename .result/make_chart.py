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



# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("Loading data...")
    sysmon = load_sysmon()
    alert  = load_alert()

    print("\n[Chart 01] Resource avg/peak 2×3")
    chart_resource_avg_peak(sysmon)

    print("\nDone. All outputs in: charts/")


if __name__ == "__main__":
    main()
