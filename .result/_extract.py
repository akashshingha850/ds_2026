import json, os, statistics

BASE = "/Users/akash/Documents/github/ds_2026/.result/json"
SCENARIOS = {"A": "scenario_A", "B1": "scenario_B1", "B2": "scenario_B2"}

def _stats(vals):
    c = [v for v in vals if v is not None and v > 0]
    if not c: return None
    return {"avg": statistics.mean(c), "std": statistics.stdev(c) if len(c)>1 else 0,
            "min": min(c), "max": max(c), "p95": sorted(c)[int(len(c)*0.95)]}

print("=== SYSMON ===")
for sc, folder in SCENARIOS.items():
    d = os.path.join(BASE, folder)
    for f in sorted(os.listdir(d)):
        if not f.endswith("_sysmon.json"): continue
        node = f.replace("_sysmon.json","")
        doc = json.load(open(os.path.join(d,f)))
        s = doc["summary"]
        samples = doc.get("samples",[])
        mem_total = samples[0].get("mem_total_gb","?") if samples else "?"
        mem_avg   = statistics.mean([x["mem_used_gb"] for x in samples if x.get("mem_used_gb")]) if samples else 0
        print(f"  {sc}/{node}: cpu avg={s['cpu_pct']['avg']:.1f} max={s['cpu_pct']['max']:.1f}  "
              f"mem_pct avg={s['mem_pct']['avg']:.1f} max={s['mem_pct']['max']:.1f}  "
              f"mem_used_avg={mem_avg:.2f}GB mem_total={mem_total}GB  "
              f"temp avg={s['temp_c']['avg']:.1f} max={s['temp_c']['max']:.1f}")

print("\n=== DETECTION ===")
for sc, folder in SCENARIOS.items():
    d = os.path.join(BASE, folder)
    for f in sorted(os.listdir(d)):
        if "detection" not in f or not f.endswith(".json"): continue
        doc = json.load(open(os.path.join(d,f)))
        evts = doc["events"].get("detections",[])
        infer = [e["inference_ms"] for e in evts if e.get("inference_ms")]
        decode= [e["decode_ms"]    for e in evts if e.get("decode_ms")]
        qa    = [e["queue_age_s"]  for e in evts if e.get("queue_age_s") is not None and e["queue_age_s"]>0]
        si = _stats(infer); sd = _stats(decode); sq = _stats(qa)
        svc  = f.replace(".json","").split("_",1)[1]
        node = doc["summary"].get("node_id","?")
        if si:
            print(f"  {sc}/{node}/{svc}: n={len(infer)} infer avg={si['avg']:.1f}+-{si['std']:.1f} max={si['max']:.1f}ms  "
                  f"decode avg={sd['avg']:.1f}ms  queue_age avg={sq['avg']:.3f} max={sq['max']:.3f}s")

print("\n=== ALERT ===")
for sc, folder in SCENARIOS.items():
    path = os.path.join(BASE, folder, "pi3_alert.json")
    doc = json.load(open(path))
    s   = doc["summary"]
    print(f"  {sc}: recv={s.get('images_received')} with_det={s.get('images_with_detections')} "
          f"orphans={s.get('orphan_events')} alerts_sent={s.get('alerts_sent')} tg={s.get('telegram_acks')}")
    qa  = s.get("queue_age_s",{})
    e2e = s.get("e2e_latency_s",{})
    print(f"       queue_age avg={qa.get('avg',0):.3f} min={qa.get('min',0):.3f} max={qa.get('max',0):.3f} p95={qa.get('p95',0):.3f}")
    print(f"       e2e_recv_to_alert avg={e2e.get('avg',0):.3f} max={e2e.get('max',0):.3f} p95={e2e.get('p95',0):.3f}")
    evts = doc["events"].get("image_received",[])
    full    = sum(1 for e in evts if e.get("detection_ts") and e["detection_ts"]!="None")
    partial = sum(1 for e in evts if not e.get("detection_ts") or e["detection_ts"]=="None")
    print(f"       full={full} partial={partial} total={full+partial}")
    # dispatch_s stats
    disp = [e["latency"]["dispatch_s"] for e in evts if e.get("latency") and e["latency"].get("dispatch_s") is not None and e["latency"]["dispatch_s"]>0]
    sd2 = _stats(disp)
    if sd2: print(f"       dispatch avg={sd2['avg']:.3f} max={sd2['max']:.3f}s")

print("\n=== MOTION ===")
for sc, folder in SCENARIOS.items():
    d = os.path.join(BASE, folder)
    for f in os.listdir(d):
        if "motion" not in f or not f.endswith(".json"): continue
        doc = json.load(open(os.path.join(d,f)))
        s   = doc["summary"]
        evts= doc["events"].get("motion_events",[])
        kb  = [e["size_kb"] for e in evts if e.get("size_kb")]
        if kb:
            print(f"  {sc}: node={s.get('node_id')} published={s.get('images_published')} "
                  f"img avg={statistics.mean(kb):.1f}KB min={min(kb):.1f} max={max(kb):.1f}KB")
