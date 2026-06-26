"""Shared helpers for the ROS 2 services (motion / detection / alert).

This module is intentionally free of any ZeroMQ dependency so the ROS 2 service
images do not need ``pyzmq`` installed. The legacy ZeroMQ services
(``system_monitor``, ``report``) keep using ``shared/utils.py`` and its
``ZMQNode``; this module only provides the hostname resolution and logging
setup that every service shares.
"""

import logging
import os
import re
import socket


def ros_namespace():
    """Return a ROS 2-safe per-device namespace derived from the hostname.

    ROS 2 names only allow ``[A-Za-z0-9_]`` tokens (no hyphens), so the
    hostname is sanitized (e.g. ``ubuntu-RTX2080`` -> ``ubuntu_RTX2080``).
    All nodes on the same device share this namespace, so the on-device
    motion -> detection -> alert topics line up under ``/<hostname>/...``.
    Override with the ``ROS_NS`` env var if needed.
    """
    raw = os.getenv("ROS_NS") or resolve_device_hostname()
    ns = re.sub(r"[^A-Za-z0-9_]", "_", raw)
    if not ns:
        ns = "device"
    if ns[0].isdigit():
        ns = "_" + ns
    return ns


def resolve_device_hostname():
    """Return the host machine hostname.

    Prefers the bind-mounted ``/host_hostname`` (set in docker-compose) so that
    containers report the physical node name rather than the container id.
    """
    for path in ("/host_hostname", "/etc/hostname"):
        try:
            with open(path, "r") as f:
                host_name = f.read().strip()
                if host_name:
                    return host_name
        except Exception:
            pass
    return socket.gethostname()


def setup_logging():
    """Configure logging to a hostname-specific file plus the console.

    Mirrors the behaviour previously provided as a side effect of importing
    ``shared/utils.py`` so log output is unchanged after the ROS 2 migration.
    Returns the resolved device hostname for convenience.
    """
    os.makedirs("logs", exist_ok=True)
    device_hostname = resolve_device_hostname()
    logging.basicConfig(
        filename=f"logs/{device_hostname}.log",
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        force=True,
    )
    root_logger = logging.getLogger("")
    has_stream_handler = any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
        for handler in root_logger.handlers
    )
    if not has_stream_handler:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        root_logger.addHandler(console)
    return device_hostname
