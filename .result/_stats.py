import json, glob, os

base = ".result/json"

print("=== SYSMON ===")
for sc in ["A","B1","B2"]:
    print(f"\n--- Scenario {sc} ---")
    for f in sorted(glob.glob(f"{base}/scenario_{sc}/*sysmon*.json")):
        with open(f) as fh: d = json.load(fh)
        s = d["summary"]
        node = os.path.basename(f).replace("_sysmon.json","")
        nu = s.get("net_upload_kbps",{})
        nd = s.get("net_download_kbps",{})
        print(f"  {node}: cpu_avg={s['cpu_pct']['avg']:.2f} cpu_max={s['cpu_pct']['max']} "
              f"mem_avg={s['mem_pct']['avg']:.2f} mem_max={s['mem_pct']['max']} "
              f"temp_avg={s['temp_c']['avg']:.2f} temp_max={s['temp_c']['max']} "
              f"disk_r_avg={s['disk_read_kbps']['avg']:.1f} disk_r_max={s['disk_read_kbps']['max']} "
              f"disk_w_avg={s['disk_write_kbps']['avg']:.1f} disk_w_max={s['disk_write_kbps']['max']} "
              f"net_up_avg={nu.get('avg',0):.3f} net_up_max={nu.get('max',0)} "
              f"net_dl_avg={nd.get('avg',0):.3f} net_dl_max={nd.get('max',0)}")

print("\n\n=== DETECTION ===")
for sc in ["A","B1","B2"]:
    print(f"\n--- Scenario {sc} ---")
    for f in sorted(glob.glob(f"{base}/scenario_{sc}/*detection*.json")):
        with open(f) as fh: d = json.load(fh)
        s = d["summary"]
        name = os.path.basename(f).replace(".json","")
        print(f"  {name}: n={s['images_processed']} infer_avg={s['inference_ms']['avg']:.1f} "
              f"infer_max={s['inference_ms']['max']:.1f} infer_p95={s['inference_ms']['p95']:.1f} "
              f"decode_avg={s['decode_ms']['avg']:.1f}")

print("\n\n=== ALERT ===")
for sc in ["A","B1","B2"]:
    print(f"\n--- Scenario {sc} ---")
    with open(f"{base}/scenario_{sc}/pi3_alert.json") as fh: d = json.load(fh)
    s = d["summary"]
    print(f"  recv={s['images_received']} with_det={s['images_with_detections']} orphans={s['orphan_events']} "
          f"alerts={s['alerts_sent']} tg={s['telegram_acks']}")
    print(f"  queue_age: avg={s['queue_age_s']['avg']:.3f} max={s['queue_age_s']['max']:.3f} p95={s['queue_age_s']['p95']:.3f}")
    print(f"  e2e_lat:   avg={s['e2e_latency_s']['avg']:.3f} max={s['e2e_latency_s']['max']:.3f} p95={s['e2e_latency_s']['p95']:.3f}")
    print(f"  det_lat:   avg={s['detect_latency_s']['avg']:.3f} max={s['detect_latency_s']['max']:.3f} p95={s['detect_latency_s']['p95']:.3f}")

print("\n\n=== MOTION ===")
for sc in ["A","B1","B2"]:
    for f in glob.glob(f"{base}/scenario_{sc}/*motion*.json"):
        with open(f) as fh: d = json.load(fh)
        s = d["summary"]
        name = os.path.basename(f)
        print(f"  {sc}/{name}: published={s['images_published']}")
