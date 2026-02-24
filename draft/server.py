"""
Run with: streamlit run server.py

"""
import zmq
import threading
import sys
import time
from datetime import datetime
from draft.config import SYSTEM_MONITOR_PORT, SYSTEM_MONITOR_INTERVAL, DISCOVERY_PORT_SYSTEM
from collections import deque
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Add parent directory to path to import config
sys.path.append('.')
from utils import ZMQNode
# --- Backend: Data Collection (Cached Resource) ---
@st.cache_resource
class DataCollector(ZMQNode):
    def __init__(self):
        ZMQNode.__init__(self, 'server', discovery_port=DISCOVERY_PORT_SYSTEM)
        self.data = {}  # dict of node_id -> deque
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._subscriber_thread, daemon=True)
        self.discovery_thread = threading.Thread(target=self.discovery_loop, daemon=True)
        self.thread.start()
        self.discovery_thread.start()
        print("DataCollector started")

    def _subscriber_thread(self):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        connected_ips = set()
        print("[DEBUG] Subscriber thread started.")
        while self.running:
            # Check for new system_monitor peers and connect
            for peer_id, info in list(self.peers_info.items()):
                print(f"[DEBUG] Checking peer: {peer_id}, info: {info}")
                if 'system_monitor' in peer_id and info['ip'] not in connected_ips:
                    try:
                        socket.connect(f"tcp://{info['ip']}:{SYSTEM_MONITOR_PORT}")
                        connected_ips.add(info['ip'])
                        print(f"[DEBUG] Connected to {info['ip']}:{SYSTEM_MONITOR_PORT}")
                    except Exception as e:
                        print(f"[DEBUG] Failed to connect to {info['ip']}: {e}")
            # Receive messages
            try:
                if socket.poll(1000):
                    msg = socket.recv_json()
                    print(f"[DEBUG] Received message: {msg}")
                    node_id = msg.get('node_id')
                    if node_id:
                        with self.lock:
                            if node_id not in self.data:
                                self.data[node_id] = deque(maxlen=60)
                            self.data[node_id].append(msg)
            except Exception as e:
                print(f"[DEBUG] Error accessing socket: {e}")
                time.sleep(1)
        socket.close()
        context.term()

    def get_dataframe(self, node_id):
        with self.lock:
            if node_id not in self.data or not self.data[node_id]:
                return pd.DataFrame()
            df = pd.DataFrame(list(self.data[node_id]))
            if not df.empty and 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
                # Removed GPU column processing as 'gpu' is not present in the data
                df['numeric_temp'] = df['temperature'].apply(lambda x: float(x.rstrip('°C')) if isinstance(x, str) and x.endswith('°C') and 'not available' not in x.lower() else float('nan'))
            return df
            
    def get_latest(self, node_id):
        with self.lock:
            return self.data[node_id][-1] if node_id in self.data and self.data[node_id] else None

# Initialize the collector (singleton)
collector = DataCollector()

# --- Frontend: Dashboard ---
def run_dashboard():
    st.set_page_config(page_title="System Monitor", layout="wide")
    st.title("Live System Monitor (Last 60s)")
    
    with collector.lock:
        node_ids = list(collector.data.keys())
    
    if not node_ids:
        st.warning("Waiting for data... Ensure system_monitor.py is running on at least one device.")
        time.sleep(1)
        st.rerun()
        return

    tabs = st.tabs([f"Node: {node_id}" for node_id in node_ids])
    
    for i, node_id in enumerate(node_ids):
        with tabs[i]:
            df = collector.get_dataframe(node_id)
            latest = collector.get_latest(node_id)

            if df.empty:
                st.warning(f"No data for {node_id}")
                continue

            st.subheader(f"Node ID: {node_id}")

            # Metrics Row
            cols = st.columns(4)
            cols[0].metric("CPU", f"{latest.get('cpu', 0):.1f}%")
            cols[1].metric("Memory", f"{latest.get('memory_used_gb', 0):.1f}/{latest.get('memory_total_gb', 0):.1f} GB")
            cols[2].metric("Temp", f"{latest.get('temperature', 'N/A')}")
            cols[3].metric("GPU", f"{latest.get('gpu', 'N/A')}")

            st.divider()

            # I/O Metrics Row
            cols2 = st.columns(4)
            cols2[0].metric("Disk Read", f"{latest.get('disk_read_kbs', 0):.1f} KB/s")
            cols2[1].metric("Disk Write", f"{latest.get('disk_write_kbs', 0):.1f} KB/s")
            cols2[2].metric("Net Recv", f"{latest.get('network_recv_kbs', 0):.1f} KB/s")
            cols2[3].metric("Net Send", f"{latest.get('network_send_kbs', 0):.1f} KB/s")

            # Charts Row
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("System Metrics")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['timestamp'], y=df['cpu'], name='CPU %'))
                fig.add_trace(go.Scatter(x=df['timestamp'], y=df['memory_percent'], name='RAM %'))
                # Removed GPU plot as 'numeric_gpu' is not present in the data
                fig.add_trace(go.Scatter(x=df['timestamp'], y=df['numeric_temp'], name='Temp °C'))
                fig.update_layout(
                    yaxis=dict(title='Usage (%) / Temp (°C)', range=[0, 100]),
                    height=300, margin=dict(l=0, r=0, t=30, b=0)
                )
                st.plotly_chart(fig, width='stretch')

            with col2:
                st.subheader("I/O Metrics (KB/s)")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['timestamp'], y=df['network_recv_kbs'], name='Net Recv'))
                fig.add_trace(go.Scatter(x=df['timestamp'], y=df['network_send_kbs'], name='Net Send'))
                fig.add_trace(go.Scatter(x=df['timestamp'], y=df['disk_read_kbs'], name='Disk Read', yaxis='y2'))
                fig.add_trace(go.Scatter(x=df['timestamp'], y=df['disk_write_kbs'], name='Disk Write', yaxis='y2'))
                fig.update_layout(
                    yaxis=dict(title='Network (KB/s)'),
                    yaxis2=dict(title='Disk (KB/s)', overlaying='y', side='right'),
                    height=300, margin=dict(l=0, r=0, t=30, b=0)
                )
                st.plotly_chart(fig, width='stretch')

    # Auto-refresh loop
    time.sleep(SYSTEM_MONITOR_INTERVAL)
    st.rerun()

if __name__ == "__main__":
    if 'streamlit' in sys.modules:
        run_dashboard()
    else:
        # CLI starter
        import subprocess
        print("Starting Dashboard...")
        subprocess.run(["streamlit", "run", __file__, "--server.headless", "true", "--server.port", "8501"])
