# Graph Report - .  (2026-06-28)

## Corpus Check
- 82 files · ~108,442 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 488 nodes · 665 edges · 39 communities (33 shown, 6 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 84 edges (avg confidence: 0.82)
- Token cost: 209,957 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Results Charting (matplotlib)|Results Charting (matplotlib)]]
- [[_COMMUNITY_Motion Detection Node (ROS 2)|Motion Detection Node (ROS 2)]]
- [[_COMMUNITY_Config & Deployment Stack|Config & Deployment Stack]]
- [[_COMMUNITY_RTSP Streaming & Motion Guide|RTSP Streaming & Motion Guide]]
- [[_COMMUNITY_Peer Discovery PubSub Nodes|Peer Discovery PubSub Nodes]]
- [[_COMMUNITY_Recorder & Streamlit Dashboard|Recorder & Streamlit Dashboard]]
- [[_COMMUNITY_Alert Pipeline Architecture|Alert Pipeline Architecture]]
- [[_COMMUNITY_System Monitor Metrics|System Monitor Metrics]]
- [[_COMMUNITY_Alert Manager Service|Alert Manager Service]]
- [[_COMMUNITY_Detection Processing Node|Detection Processing Node]]
- [[_COMMUNITY_Swarm Rebalancer Script|Swarm Rebalancer Script]]
- [[_COMMUNITY_Log Parsing & Aggregation|Log Parsing & Aggregation]]
- [[_COMMUNITY_DS Architecture & ROS 2 Messaging|DS Architecture & ROS 2 Messaging]]
- [[_COMMUNITY_Resource & Delay Time-series|Resource & Delay Time-series]]
- [[_COMMUNITY_Draft ZeroMQ Detection Processor|Draft ZeroMQ Detection Processor]]
- [[_COMMUNITY_ZeroMQ Image Publisher|ZeroMQ Image Publisher]]
- [[_COMMUNITY_Draft ZeroMQ Detection|Draft ZeroMQ Detection]]
- [[_COMMUNITY_Rebalancing & Resource Charts|Rebalancing & Resource Charts]]
- [[_COMMUNITY_Draft Alerting Manager|Draft Alerting Manager]]
- [[_COMMUNITY_ZeroMQ Image Subscriber|ZeroMQ Image Subscriber]]
- [[_COMMUNITY_ZeroMQ JPEG Subscriber|ZeroMQ JPEG Subscriber]]
- [[_COMMUNITY_Inference Latency Charts|Inference Latency Charts]]
- [[_COMMUNITY_OpenCV Motion Processing|OpenCV Motion Processing]]
- [[_COMMUNITY_Draft YOLO Detection Script|Draft YOLO Detection Script]]
- [[_COMMUNITY_YOLO Demo Images (Madrid Bus)|YOLO Demo Images (Madrid Bus)]]
- [[_COMMUNITY_Draft System Monitor|Draft System Monitor]]
- [[_COMMUNITY_Flask Event API|Flask Event API]]
- [[_COMMUNITY_Config Loader|Config Loader]]
- [[_COMMUNITY_Server Tests|Server Tests]]
- [[_COMMUNITY_Stack Deploy Script|Stack Deploy Script]]
- [[_COMMUNITY_Compose Watch Hot-Reload|Compose Watch Hot-Reload]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]

## God Nodes (most connected - your core abstractions)
1. `save_chart()` - 12 edges
2. `ZMQNode` - 11 edges
3. `AlertManager` - 11 edges
4. `AlertManager` - 10 edges
5. `Distributed Surveillance System` - 10 edges
6. `Motion Detection on RTSP Streams Guide` - 10 edges
7. `DetectionProcessor` - 9 edges
8. `main()` - 9 edges
9. `AlertNode` - 9 edges
10. `DetectionProcessor` - 9 edges

## Surprising Connections (you probably didn't know these)
- `ZeroMQ pub/sub (system_monitor)` --conceptually_related_to--> `Deep Log Analysis Report`  [AMBIGUOUS]
  README.md → .result/analysis.md
- `SIYI A8 Mini IP Camera` --references--> `SIYI A8 Mini User Manual v1.10`  [INFERRED]
  README.md → report/A8 mini User Manual v1.10 .pdf
- `Motion Detection on RTSP Streams Guide` --semantically_similar_to--> `Motion Detection System (ROS 2)`  [INFERRED] [semantically similar]
  .draft/motion/motion.md → motion/motion.md
- `BaseNode` --semantically_similar_to--> `ZMQNode`  [INFERRED] [semantically similar]
  .draft/record.md → system_monitor/system_monitor.md
- `main()` --calls--> `setup_logging()`  [INFERRED]
  alert/alert.py → shared/ros_common.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Motion to Detection to Alert ROS 2 pipeline** — readme_motion_service, readme_detection_coco_service, readme_detection_fire_service, readme_alert_service, readme_ros2_humble_messaging [EXTRACTED 1.00]
- **Three-stage surveillance task decomposition** — report_task_frame_motion, report_task_object_detection, report_task_alarming [EXTRACTED 1.00]
- **Publish-subscribe coordination concepts** — architecture_lecture_publish_subscribe, architecture_lecture_event_based_coordination, architecture_lecture_middleware [EXTRACTED 1.00]
- **Motion-to-Detection-to-Record Pipeline** — mediamtx_mediamtx_path_stream, motion_motion_system, yolo26n_ncnn_model_metadata, record_video_recorder [INFERRED 0.75]
- **Motion Detection Techniques Catalog** — motion_motion_draft_frame_differencing, motion_motion_draft_background_subtraction, motion_motion_draft_optical_flow, motion_motion_draft_deep_learning_temporal [EXTRACTED 1.00]
- **YOLO26n NCNN Inference Artifacts** — yolo26n_ncnn_model_metadata, yolo_detection_results, yolo_detection_results_ncnn [INFERRED 0.85]

## Communities (39 total, 6 thin omitted)

### Community 0 - "Results Charting (matplotlib)"
Cohesion: 0.07
Nodes (40): Figure, chart_alert_pipeline(), chart_assembly_breakdown(), chart_e2e_timeseries(), chart_inference_boxplot(), chart_latency_cdf(), chart_resource_avg_peak(), chart_resource_timeseries() (+32 more)

### Community 1 - "Motion Detection Node (ROS 2)"
Cohesion: 0.08
Nodes (24): get_video_dimensions(), main(), MotionDetector, Probe the video stream and return width and height., Node, BaseNode, Shared helpers for the ROS 2 services (motion / detection / alert / system_monit, Return a ROS 2-safe per-device namespace derived from the hostname.      ROS 2 n (+16 more)

### Community 2 - "Config & Deployment Stack"
Cohesion: 0.10
Nodes (34): YOLO26n COCO model (80 classes), Env-var override of config defaults, Unified config.yaml, Detection Python dependencies (torch, ncnn, ultralytics), DETECTOR env selects model, docker-compose stack (ds_2026), YOLO26n Fire model (smoke/fire), Edge ML/LLM real-time inference (+26 more)

### Community 3 - "RTSP Streaming & Motion Guide"
Cohesion: 0.09
Nodes (29): MediaMTX playback path, MediaMTX stream path, MediaMTX Recording, MediaMTX RTSP Server, MediaMTX Media Server, Motion config.py Parameters, MotionDetector Class, Background Subtraction (MOG2/KNN) (+21 more)

### Community 4 - "Peer Discovery PubSub Nodes"
Cohesion: 0.10
Nodes (15): discovery_loop(), get_local_ip(), main(), discovery_loop(), get_local_ip(), main(), Minimal Peer Node - Auto-discovery + PUB/SUB status updates, Minimal Peer Node - Auto-discovery + status updates (+7 more)

### Community 5 - "Recorder & Streamlit Dashboard"
Cohesion: 0.10
Nodes (9): Record a 15-second clip using FFmpeg., Listen for motion flags and trigger recordings., Handle motion flag messages., Recorder, DataCollector, Run with: streamlit run server.py, run_dashboard(), Discover a peer by node_id suffix (e.g., '-motion', '-system_monitor'). (+1 more)

### Community 6 - "Alert Pipeline Architecture"
Cohesion: 0.14
Nodes (24): Alerts Dispatched, Alert Pipeline Stage Counts per Scenario, Images Received, Orphan Events, Test Scenario (A/B1/B2), Telegram ACKs, With Detections, Alert Manager (+16 more)

### Community 7 - "System Monitor Metrics"
Cohesion: 0.12
Nodes (13): get_cpu_status(), get_disk_status_static(), get_memory_status(), get_network_status_static(), get_speeds(), get_temperature_status(), Publish system status via ZeroMQ., Get CPU usage percentage. (+5 more)

### Community 8 - "Alert Manager Service"
Cohesion: 0.18
Nodes (4): AlertManager, AlertNode, main(), Flush image events that never received a correlated detection in time.

### Community 9 - "Detection Processing Node"
Cohesion: 0.17
Nodes (9): discovery_loop(), get_local_ip(), process_aggregated_event(), subscriber_loop(), DetectionProcessor, main(), Load the YOLO model from the given path., Run inference on the image using the model. (+1 more)

### Community 10 - "Swarm Rebalancer Script"
Cohesion: 0.25
Nodes (11): rebalancer.sh script, clear_cooldowns(), do_rebalance(), force_redistribute_service(), is_in_cooldown(), log(), log_debug(), log_info() (+3 more)

### Community 11 - "Log Parsing & Aggregation"
Cohesion: 0.16
Nodes (13): classify_log(), parse_app_log(), parse_iso(), parse_log_ts(), parse_sysmon(), convert_logs_to_json.py ----------------------- Parses all raw log files (applic, Return (node, log_type) based on filename., Parse system monitor log → list of metric samples. (+5 more)

### Community 12 - "DS Architecture & ROS 2 Messaging"
Cohesion: 0.16
Nodes (14): DS Architecture Lecture (Lecture 2), Event-based coordination, Layered architectural style, Middleware layer, Peer-to-peer distribution, Publish-subscribe architectural style, Software architecture, System architecture (+6 more)

### Community 13 - "Resource & Delay Time-series"
Cohesion: 0.24
Nodes (12): CPU Temperature (C), CPU Utilisation (%), CPU Utilisation and Temperature Over Time per Node, Per-Node Load Distribution (pi3, pi4, pi5), Insight: Load shifts between Pi nodes across scenarios; CPU spikes drive corresponding temperature rises (up to ~70C in B2), Scenario Comparison (A, B1, B2), Communication Delay, Dispatch Delay (+4 more)

### Community 14 - "Draft ZeroMQ Detection Processor"
Cohesion: 0.21
Nodes (5): DetectionProcessor, Load the YOLO model from the given path., Run inference on the image using the model., Save YOLO-annotated result image to disk., Publish detection results via ZeroMQ.

### Community 15 - "ZeroMQ Image Publisher"
Cohesion: 0.23
Nodes (11): base64_to_image(), discovery_loop(), get_local_ip(), image_to_base64(), main(), publish_image(), Image Publisher - Publish images via ZeroMQ PUB/SUB, Convert image file to base64 string (+3 more)

### Community 16 - "Draft ZeroMQ Detection"
Cohesion: 0.21
Nodes (11): discovery_loop(), get_local_ip(), load_model(), print_results(), Load the YOLO model from the given path., Run inference on the image using the model., Print the detection results to the console., Save the detection results to a text file and annotated image. (+3 more)

### Community 17 - "Rebalancing & Resource Charts"
Cohesion: 0.22
Nodes (11): Detect overloaded nodes and redeploy eligible services to idle nodes on each polling cycle, Force Redeployment of Service to Idle Node, Rebalancing Control Loop Flowchart, Imbalance Detection, Periodic Poll Loop (Sleep Δt_poll), CPU Usage (%), CPU / RAM / Temperature Average vs Peak per Node and Scenario, pi3 carries heaviest load (CPU peaks 94-95% in B1/B2); peak CPU/RAM/temp far exceed averages indicating bursty load (+3 more)

### Community 19 - "ZeroMQ Image Subscriber"
Cohesion: 0.27
Nodes (9): base64_to_image(), discovery_loop(), get_local_ip(), main(), Image Subscriber - Receive and save images from ZeroMQ PUB, Discover and announce this node to peers, Convert base64 string back to image file, Subscribe to and receive images from peers (+1 more)

### Community 20 - "ZeroMQ JPEG Subscriber"
Cohesion: 0.27
Nodes (9): discovery_loop(), get_local_ip(), main(), Image Subscriber - Receive and save images from ZeroMQ PUB, Discover and announce this node to peers, Save raw JPEG bytes to a file, Subscribe to and receive images from peers, save_jpeg_bytes() (+1 more)

### Community 21 - "Inference Latency Charts"
Cohesion: 0.28
Nodes (9): COCO Detector Model, Fire Detector Model, Inference Latency Distribution per Scenario and Model (Boxplot), Inference Time (ms), Scenario B2 highest median latency and widest spread, End-to-End Latency / Queue Age (s), Queue Age / E2E Latency CDF by Scenario, P50 / P95 Latency Percentiles (+1 more)

### Community 22 - "OpenCV Motion Processing"
Cohesion: 0.44
Nodes (8): Mat, build_capture(), compute_motion_ratio(), main(), preprocess_frame(), process_stream(), read_frame(), VideoCapture

### Community 23 - "Draft YOLO Detection Script"
Cohesion: 0.22
Nodes (8): load_model(), print_results(), Run inference on the image using the model., Print the detection results to the console., Save the detection results to a text file and annotated image., Load the YOLO model from the given path., run_inference(), save_results()

### Community 24 - "YOLO Demo Images (Madrid Bus)"
Cohesion: 0.43
Nodes (8): EMT Madrid Electric Minibus (Cero Emisiones), Street Photo: EMT Madrid Electric Bus, Pedestrians on Madrid Street, Street Photo Copy: EMT Madrid Electric Bus (YOLO input), Detected Class: bus (0.90), YOLO Detection Result: Annotated Bus Scene, YOLO Object Detection with Bounding Boxes, Detected Class: person (0.84-0.85, 0.56)

### Community 25 - "Draft System Monitor"
Cohesion: 0.32
Nodes (7): get_gpu_usage(), get_temperature(), main(), parse_args(), Get CPU temperature in Celsius., Get GPU usage percentage (Raspberry Pi specific)., Namespace

### Community 27 - "Config Loader"
Cohesion: 0.40
Nodes (5): _coerce(), _find_config(), _load(), Locate config.yaml.      In the container both config.py and config.yaml are cop, Coerce an env-var string to the type of its YAML default.

### Community 30 - "Compose Watch Hot-Reload"
Cohesion: 0.67
Nodes (3): detection_coco service watch, motion service watch, Docker Compose Watch Hot-Reload Config

## Ambiguous Edges - Review These
- `ZeroMQ pub/sub (system_monitor)` → `Deep Log Analysis Report`  [AMBIGUOUS]
  .result/analysis.md · relation: conceptually_related_to

## Knowledge Gaps
- **34 isolated node(s):** `zswarm-dashboard service`, `Telegram alert dispatch`, `Root Python dependencies`, `Software architecture`, `System architecture` (+29 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `ZeroMQ pub/sub (system_monitor)` and `Deep Log Analysis Report`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `BaseNode` connect `Motion Detection Node (ROS 2)` to `RTSP Streaming & Motion Guide`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `ZMQNode` (e.g. with `DetectionProcessor` and `Recorder`) actually correct?**
  _`ZMQNode` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Load the YOLO model from the given path.`, `Run inference on the image using the model.`, `Save YOLO-annotated result image to disk.` to the rest of the system?**
  _125 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Results Charting (matplotlib)` be split into smaller, more focused modules?**
  _Cohesion score 0.0664451827242525 - nodes in this community are weakly interconnected._
- **Should `Motion Detection Node (ROS 2)` be split into smaller, more focused modules?**
  _Cohesion score 0.08108108108108109 - nodes in this community are weakly interconnected._
- **Should `Config & Deployment Stack` be split into smaller, more focused modules?**
  _Cohesion score 0.09803921568627451 - nodes in this community are weakly interconnected._