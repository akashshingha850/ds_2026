"""
convert_logs_to_json.py
-----------------------
Parses all raw log files (application + system-monitor) for every scenario
and writes structured JSON files to logs/json/.

Each physical log file can contain multiple co-located services
(e.g. pi3.log in B1/B2 has both alert + motion; pi4.log in B2 has
detection_coco + detection_fire).  The parser splits them into separate
JSON files, one per service.

Output structure:
  logs/json/
    scenario_A/
      pi3_alert.json
      pi4_detection_coco.json
      pi5_detection_fire.json
      pi5_motion.json
      pi3_sysmon.json  pi4_sysmon.json  pi5_sysmon.json
    scenario_B1/
      pi3_alert.json  pi3_motion.json
      pi5_detection_coco.json
      pi3_sysmon.json  pi5_sysmon.json
    scenario_B2/
      pi3_alert.json  pi3_motion.json
      pi4_detection_coco.json  pi4_detection_fire.json
      pi3_sysmon.json  pi4_sysmon.json
    index.json
"""

import re
import os
import json
from datetime import datetime
from collections import defaultdict

# ── paths ─────────────────────────────────────────────────────────────────────
BASE      = os.path.dirname(os.path.abspath(__file__))
OUT_ROOT  = os.path.join(BASE, "json")

SCENARIOS = {
    "scenario_A":  os.path.join(BASE, "Senario A - pi3+pi4+pi5"),
    "scenario_B1": os.path.join(BASE, "senario B1 - pi3+pi5"),
    "scenario_B2": os.path.join(BASE, "senario B2 - p3+pi4"),
}

# ── regex patterns ─────────────────────────────────────────────────────────────
TS_PREFIX = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (.+)$')

# Alert log patterns
RE_IMG_RECV = re.compile(
    r'received Image #(\d+) from \[([^\]]+)\]'
    r' - Event TS: ([\d:.]+)'
    r' - Recv TS: ([\w\-:.T]+)'
    r' - Detection TS: ([\w\-:.T]+)'
    r' - Alert Send TS: ([\w\-:.T]+)'
    r' - Queue Age: ([\d.]+)s'
    r' - Detections: (\d+)'
)
RE_IMG_QUEUED  = re.compile(r'Queued image event for sender=([\w-]+), image_id=(\d+)')
RE_CORRELATED  = re.compile(r'Correlated detection_results for sender=([\w-]+), image_id=(\d+)')
RE_NO_PENDING  = re.compile(r'No pending event found for sender=([\w-]+), image_id=(\d+)')
RE_ALERT_SENT  = re.compile(r'(\w+) SENT ALERT.*?Send TS: ([\w\-:.T]+).*?Payload: (.+)$')
RE_TELEGRAM_OK = re.compile(r'\[ALERT_SEND\] Telegram sent successfully - status=(\d+)')
RE_SUBSCRIBED  = re.compile(r'\[SUB:([\w-]+)\] Subscribing to messages on port (\d+)')
RE_CONNECTED   = re.compile(r'\[([^\]]+)\] Connected to ([\w-]+) at (tcp://[^\s]+)')

# Detection log patterns
RE_DET_RECV = re.compile(
    r'([\w-]+) received image #(\d+) from ([\w-]+)'
    r' - Send TS: ([\d:.]+)'
    r' - Recv TS: ([\w\-:.T]+)'
    r' - Detect TS: ([\w\-:.T]+)'
    r' - Queue Age: ([\d.]+)s'
    r' - Decode: ([\d.]+)ms'
    r' - Inference: ([\d.]+)ms'
    r' - Results: (\d+) detections'
)
RE_DET_PUB = re.compile(r'([\w-]+) Published Image #(\d+) results: (\[.+\])')

# Motion publisher patterns
RE_MOT_PUB_START  = re.compile(r'\[(FLAG_PUB|IMAGE_PUB|PUB):([\w-]+)\] (.+)')
RE_MOT_START      = re.compile(r'([\w-]+) Starting motion detection')
RE_MOT_PUBLISHED  = re.compile(r'([\w-]+) published image #(\d+) \(([\d.]+) KB\) at ([\d:.]+)')
RE_MOT_EVT        = re.compile(r'\[([\w-]+)\] Motion (detected|stopped)')

# System monitor patterns
RE_SYSMON = re.compile(
    r'Node ID: ([\w-]+), CPU: ([\d.]+)%, Memory: ([\d.]+)/([\d.]+) GB \(([\d.]+)%\),'
    r' Temp: ([\d.]+)°C, Disk R/W: ([\d.]+)/([\d.]+) KB/s, Network U/D: ([\d.]+)/([\d.]+) KB/s'
)

# ── helpers ───────────────────────────────────────────────────────────────────
def parse_log_ts(ts_str):
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S,%f").isoformat()
    except:
        return ts_str

def parse_iso(ts_str):
    try:
        return datetime.fromisoformat(ts_str).isoformat()
    except:
        return ts_str

def classify_log(filename):
    """Return (node, log_type) based on filename."""
    fname = filename.lower()
    if 'htop' in fname:
        node = fname.split('-htop')[0]
        return node, 'sysmon'
    if 'pi3' in fname: return 'pi3', 'app'
    if 'pi4' in fname: return 'pi4', 'app'
    if 'pi5' in fname: return 'pi5', 'app'
    return 'unknown', 'app'

def _fresh_service_bucket():
    return {
        "startup":       [],
        "connections":   [],
        # alert
        "image_received": [],
        "image_queued":   [],
        "correlations":   [],
        "orphan_events":  [],
        "alerts_sent":    [],
        "telegram_acks":  [],
        # detection
        "detections":    [],
        "publications":  [],
        # motion publisher
        "motion_events": [],
    }

# ── parsers ───────────────────────────────────────────────────────────────────
def parse_sysmon(lines):
    """Parse system monitor log → list of metric samples."""
    samples = []
    for line in lines:
        m = TS_PREFIX.match(line.strip())
        if not m:
            continue
        ts, body = m.groups()
        sm = RE_SYSMON.search(body)
        if sm:
            node, cpu, mem_used, mem_total, mem_pct, temp, disk_r, disk_w, net_u, net_d = sm.groups()
            samples.append({
                "ts": parse_log_ts(ts),
                "node_id": node,
                "cpu_pct":          float(cpu),
                "mem_used_gb":      float(mem_used),
                "mem_total_gb":     float(mem_total),
                "mem_pct":          float(mem_pct),
                "temp_c":           float(temp),
                "disk_read_kbps":   float(disk_r),
                "disk_write_kbps":  float(disk_w),
                "net_upload_kbps":  float(net_u),
                "net_download_kbps":float(net_d),
            })
    return samples


def parse_app_log(lines, node):
    """
    Parse a (possibly multi-service) application log.
    Returns a dict  { service_key → events_dict }
    where service_key is e.g. 'alert', 'detection_coco', 'motion', ...
    """
    # buckets keyed by canonical service name
    buckets: dict[str, dict] = {}   # service_key → event lists

    def _bucket(key):
        if key not in buckets:
            buckets[key] = _fresh_service_bucket()
            buckets[key]["_service_type"] = key
            buckets[key]["_node_id"] = node
        return buckets[key]

    def _svc_key(svc_name):
        """Map a service name string to a canonical key."""
        if "detection_coco" in svc_name: return "detection_coco"
        if "detection_fire" in svc_name: return "detection_fire"
        if "alert"          in svc_name: return "alert"
        if "api-sub"        in svc_name: return "alert"   # [SUB:pi3-api-sub]
        if "motion"         in svc_name: return "motion"
        return svc_name

    for line in lines:
        line = line.strip()
        m = TS_PREFIX.match(line)
        if not m:
            continue
        ts_raw, body = m.groups()
        ts = parse_log_ts(ts_raw)

        # ── startup / subscription ─────────────────────────────────────────
        sub_m = RE_SUBSCRIBED.search(body)
        if sub_m:
            svc, port = sub_m.groups()
            key = _svc_key(svc)
            _bucket(key)["startup"].append(
                {"ts": ts, "service": svc, "port": int(port), "event": "subscribing"})
            continue

        conn_m = RE_CONNECTED.search(body)
        if conn_m:
            src, dest, addr = conn_m.groups()
            key = _svc_key(src)
            _bucket(key)["connections"].append(
                {"ts": ts, "from": src, "to": dest, "address": addr})
            continue

        # ── motion publisher startup ────────────────────────────────────────
        mp_m = RE_MOT_PUB_START.search(body)
        if mp_m:
            _, svc, msg = mp_m.groups()
            key = _svc_key(svc)
            _bucket(key)["startup"].append(
                {"ts": ts, "service": svc, "event": msg.strip()})
            continue

        ms_m = RE_MOT_START.search(body)
        if ms_m:
            svc = ms_m.group(1)
            key = _svc_key(svc)
            _bucket(key)["startup"].append({"ts": ts, "service": svc, "event": "motion_detection_started"})
            continue

        # ── motion publisher: image published ──────────────────────────────
        mp2_m = RE_MOT_PUBLISHED.search(body)
        if mp2_m:
            svc, img_id, size_kb, send_ts = mp2_m.groups()
            key = _svc_key(svc)
            _bucket(key)["motion_events"].append({
                "ts": ts,
                "service": svc,
                "event": "published",
                "image_id": int(img_id),
                "size_kb": float(size_kb),
                "send_ts": send_ts,
            })
            continue

        mot_m = RE_MOT_EVT.search(body)
        if mot_m:
            svc, state = mot_m.groups()
            key = _svc_key(svc)
            _bucket(key)["motion_events"].append({"ts": ts, "service": svc, "state": state})
            continue

        # ── alert-node events ──────────────────────────────────────────────
        img_m = RE_IMG_RECV.search(body)
        if img_m:
            img_id, sender, evt_ts, recv_ts, det_ts, send_ts, q_age, n_det = img_m.groups()
            try:
                recv_dt = datetime.fromisoformat(recv_ts)
                det_dt  = datetime.fromisoformat(det_ts)
                snd_dt  = datetime.fromisoformat(send_ts)
                detect_s  = round((det_dt - recv_dt).total_seconds(), 4)
                dispatch_s= round((snd_dt - det_dt).total_seconds(), 4)
                e2e_s     = round((snd_dt - recv_dt).total_seconds(), 4)
            except:
                detect_s = dispatch_s = e2e_s = None
            _bucket("alert")["image_received"].append({
                "ts": ts,
                "image_id": int(img_id),
                "sender": sender,
                "event_ts": evt_ts,
                "recv_ts": parse_iso(recv_ts),
                "detection_ts": parse_iso(det_ts),
                "alert_send_ts": parse_iso(send_ts),
                "queue_age_s": float(q_age),
                "n_detections": int(n_det),
                "latency": {"detect_s": detect_s, "dispatch_s": dispatch_s,
                             "e2e_recv_to_alert_s": e2e_s},
            })
            continue

        q_m = RE_IMG_QUEUED.search(body)
        if q_m:
            sender, img_id = q_m.groups()
            _bucket("alert")["image_queued"].append(
                {"ts": ts, "sender": sender, "image_id": int(img_id)})
            continue

        cor_m = RE_CORRELATED.search(body)
        if cor_m:
            sender, img_id = cor_m.groups()
            _bucket("alert")["correlations"].append(
                {"ts": ts, "sender": sender, "image_id": int(img_id)})
            continue

        np_m = RE_NO_PENDING.search(body)
        if np_m:
            sender, img_id = np_m.groups()
            _bucket("alert")["orphan_events"].append(
                {"ts": ts, "sender": sender, "image_id": int(img_id)})
            continue

        al_m = RE_ALERT_SENT.search(body)
        if al_m:
            anode, send_ts, payload_str = al_m.groups()
            try:
                payload = json.loads(payload_str.strip())
            except:
                payload = payload_str.strip()
            _bucket("alert")["alerts_sent"].append({
                "ts": ts, "node_id": anode,
                "alert_send_ts": parse_iso(send_ts),
                "payload": payload,
            })
            continue

        tg_m = RE_TELEGRAM_OK.search(body)
        if tg_m:
            _bucket("alert")["telegram_acks"].append(
                {"ts": ts, "http_status": int(tg_m.group(1))})
            continue

        # ── detection events ───────────────────────────────────────────────
        det_m = RE_DET_RECV.search(body)
        if det_m:
            svc, img_id, src, send_ts, recv_ts, det_ts, q_age, dec_ms, inf_ms, n_res = det_m.groups()
            key = _svc_key(svc)
            _bucket(key)["detections"].append({
                "ts": ts,
                "service": svc,
                "image_id": int(img_id),
                "source_node": src,
                "send_ts": send_ts,
                "recv_ts": parse_iso(recv_ts),
                "detect_ts": parse_iso(det_ts),
                "queue_age_s": float(q_age),
                "decode_ms": float(dec_ms),
                "inference_ms": float(inf_ms),
                "n_results": int(n_res),
            })
            continue

        pub_m = RE_DET_PUB.search(body)
        if pub_m:
            svc, img_id, results_str = pub_m.groups()
            key = _svc_key(svc)
            try:
                results = json.loads(results_str.replace("'", '"'))
            except:
                results = []
            _bucket(key)["publications"].append({
                "ts": ts,
                "service": svc,
                "image_id": int(img_id),
                "results": results,
            })
            continue

    # ── clean up internal keys, strip empty lists ──────────────────────────
    result = {}
    for key, ev in buckets.items():
        svc_type = ev.pop("_service_type", key)
        node_id  = ev.pop("_node_id", node)
        clean = {k: v for k, v in ev.items() if v}   # drop empty lists
        clean["service_type"] = svc_type
        clean["node_id"] = node_id
        result[key] = clean
    return result   # { 'alert': {...}, 'motion': {...}, ... }


def summarise_service(events):
    """Build a summary dict for one service's events block."""
    svc_type = events.get("service_type", "unknown")
    summary  = {"service_type": svc_type, "node_id": events.get("node_id")}

    def _s4(lst):
        if not lst: return None
        s = sorted(lst)
        return {"avg": round(sum(s)/len(s), 4), "min": round(s[0], 4),
                "max": round(s[-1], 4), "p95": round(s[int(len(s)*0.95)], 4)}

    imgs = events.get("image_received", [])
    if imgs:
        q_ages   = [e["queue_age_s"] for e in imgs]
        e2es     = [e["latency"]["e2e_recv_to_alert_s"] for e in imgs
                    if e["latency"].get("e2e_recv_to_alert_s") is not None]
        det_lats = [e["latency"]["detect_s"] for e in imgs
                    if e["latency"].get("detect_s") is not None]
        summary["images_received"]        = len(imgs)
        summary["images_with_detections"] = sum(1 for e in imgs if e["n_detections"] > 0)
        summary["orphan_events"]          = len(events.get("orphan_events", []))
        summary["alerts_sent"]            = len(events.get("alerts_sent", []))
        summary["telegram_acks"]          = len(events.get("telegram_acks", []))
        summary["queue_age_s"]            = _s4(q_ages)
        summary["e2e_latency_s"]          = _s4(e2es)
        summary["detect_latency_s"]       = _s4(det_lats)

    dets = events.get("detections", [])
    if dets:
        inf_ms = [e["inference_ms"] for e in dets]
        dec_ms = [e["decode_ms"]    for e in dets]
        summary["images_processed"] = len(dets)
        summary["inference_ms"] = _s4(inf_ms)
        summary["decode_ms"]    = _s4(dec_ms)

    mot = events.get("motion_events", [])
    if mot:
        published = [e for e in mot if e.get("event") == "published"]
        summary["images_published"] = len(published)

    return summary


def summarise_sysmon(samples):
    """Build a summary dict for sysmon samples."""
    if not samples:
        return {}
    def _ms(key):
        vs = [s[key] for s in samples]
        return {"avg": round(sum(vs)/len(vs), 2),
                "min": round(min(vs), 2),
                "max": round(max(vs), 2)}
    return {
        "n_samples":         len(samples),
        "cpu_pct":           _ms("cpu_pct"),
        "mem_pct":           _ms("mem_pct"),
        "temp_c":            _ms("temp_c"),
        "disk_read_kbps":    _ms("disk_read_kbps"),
        "disk_write_kbps":   _ms("disk_write_kbps"),
        "net_upload_kbps":   _ms("net_upload_kbps"),
        "net_download_kbps": _ms("net_download_kbps"),
    }


# ── main ──────────────────────────────────────────────────────────────────────
index = {}

for scen_key, scen_folder in SCENARIOS.items():
    out_dir = os.path.join(OUT_ROOT, scen_key)
    os.makedirs(out_dir, exist_ok=True)
    index[scen_key] = {"folder": scen_folder, "files": {}}

    logfiles = sorted([f for f in os.listdir(scen_folder) if f.endswith(".log")])
    for lf in logfiles:
        path = os.path.join(scen_folder, lf)
        with open(path, errors="replace") as f:
            lines = f.readlines()

        node, log_type = classify_log(lf)

        if log_type == "sysmon":
            samples = parse_sysmon(lines)
            out_name = f"{node}_sysmon.json"
            doc = {
                "meta": {
                    "scenario": scen_key,
                    "source_file": lf,
                    "node": node,
                    "log_type": "sysmon",
                    "n_samples": len(samples),
                },
                "summary": summarise_sysmon(samples),
                "samples": samples,
            }
            out_path = os.path.join(out_dir, out_name)
            with open(out_path, "w") as f:
                json.dump(doc, f, indent=2, default=str)
            index[scen_key]["files"][out_name] = {
                "source": lf, "log_type": "sysmon",
                "path": os.path.relpath(out_path, BASE),
            }
            print(f"  [{scen_key}] {lf}  →  {out_name}")

        else:
            # parse into per-service buckets
            service_map = parse_app_log(lines, node)
            for svc_key, events in service_map.items():
                out_name = f"{node}_{svc_key}.json"
                doc = {
                    "meta": {
                        "scenario": scen_key,
                        "source_file": lf,
                        "node": node,
                        "log_type": "app",
                        "service_type": svc_key,
                    },
                    "summary": summarise_service(events),
                    "events": events,
                }
                out_path = os.path.join(out_dir, out_name)
                with open(out_path, "w") as f:
                    json.dump(doc, f, indent=2, default=str)
                index[scen_key]["files"][out_name] = {
                    "source": lf, "log_type": "app", "service_type": svc_key,
                    "path": os.path.relpath(out_path, BASE),
                }
                print(f"  [{scen_key}] {lf}  →  {out_name}")

# write index
index_path = os.path.join(OUT_ROOT, "index.json")
with open(index_path, "w") as f:
    json.dump(index, f, indent=2)
print(f"\nIndex written to: {index_path}")
print(f"All JSON files in: {OUT_ROOT}")
