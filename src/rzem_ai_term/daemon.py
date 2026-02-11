"""Session tracking daemon for rzem-ai-term.

This lightweight daemon runs as a systemd service and provides:
- Session logging to /var/log/rzem-ai-term/
- Health check endpoint via a unix socket
- Session metadata tracking (start time, user, tty)

This is optional -- the TUI works fine without it. The daemon adds
observability for multi-user SSH servers.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path("/var/log/rzem-ai-term")
SOCKET_DIR = Path("/run/rzem-ai-term")


def setup_logging(user: str) -> logging.Logger:
    """Configure logging to file and journal."""
    logger = logging.getLogger("rzem-ai-term-daemon")
    logger.setLevel(logging.INFO)

    # Log to stderr (captured by systemd journal)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

    # Also log to file if directory exists
    log_file = LOG_DIR / f"{user}.log"
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fh)
    except PermissionError:
        logger.warning("Cannot write to %s, file logging disabled", log_file)

    return logger


def run_daemon() -> None:
    """Run the session tracking daemon."""
    import pwd

    user = pwd.getpwuid(os.getuid()).pw_name
    logger = setup_logging(user)

    logger.info("rzem-ai-term daemon starting for user=%s pid=%d", user, os.getpid())

    # Track session info
    session_info = {
        "user": user,
        "pid": os.getpid(),
        "started": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
    }

    # Create a unix socket for health checks
    sock_path = SOCKET_DIR / f"{user}.sock"
    sock = None
    try:
        SOCKET_DIR.mkdir(parents=True, exist_ok=True)
        if sock_path.exists():
            sock_path.unlink()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(sock_path))
        sock.listen(1)
        sock.settimeout(1.0)
        logger.info("Health check socket at %s", sock_path)
    except (PermissionError, OSError) as e:
        logger.warning("Cannot create health socket: %s", e)
        sock = None

    running = True

    def handle_signal(signum, frame):
        nonlocal running
        logger.info("Received signal %d, shutting down", signum)
        running = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        while running:
            if sock is not None:
                try:
                    conn, _ = sock.accept()
                    try:
                        request = conn.recv(1024).decode()
                        if request.strip() == "status":
                            session_info["uptime_seconds"] = int(
                                time.time()
                                - datetime.fromisoformat(session_info["started"]).timestamp()
                            )
                            conn.sendall(json.dumps(session_info).encode() + b"\n")
                    finally:
                        conn.close()
                except socket.timeout:
                    pass
            else:
                time.sleep(1.0)
    finally:
        if sock is not None:
            sock.close()
            try:
                sock_path.unlink()
            except FileNotFoundError:
                pass
        logger.info("rzem-ai-term daemon stopped for user=%s", user)


def main() -> None:
    """Entry point."""
    run_daemon()


if __name__ == "__main__":
    main()
