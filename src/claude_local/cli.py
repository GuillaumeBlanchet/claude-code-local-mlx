"""
claude-local: Start a local MLX proxy and launch Claude Code against it.

Clones/updates claude-code-mlx-proxy, starts the proxy server with the
requested model, waits for it to be healthy, then launches Claude Code.

Usage:
    claude-local                                          # default model
    claude-local --model mlx-community/Some-Other-Model   # custom model
    claude-local --server                                 # proxy only
    claude-local --kill                                   # kill proxy
    claude-local --restart                                # force restart proxy
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── Defaults ────────────────────────────────────────────────────────────────
PROXY_REPO = "https://github.com/chand1012/claude-code-mlx-proxy.git"
DATA_DIR = Path.home() / ".local" / "share" / "claude-local"
PROXY_DIR = DATA_DIR / "proxy"
STATE_DIR = Path.home() / ".local" / "state"
PIDFILE = STATE_DIR / "claude-mlx-proxy.pid"
LOGFILE = STATE_DIR / "claude-mlx-proxy.log"
DEPS_UPGRADED_MARKER = PROXY_DIR / ".deps-upgraded"

DEFAULT_MODEL = "mlx-community/Qwen3-Coder-Next-8bit"
DEFAULT_PORT = 18808


# ── Helpers ─────────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    print(f"[claude-local] {msg}", flush=True)


def read_pid() -> int | None:
    try:
        pid = int(PIDFILE.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return None


def kill_existing() -> None:
    pid = read_pid()
    if pid:
        log(f"Killing existing proxy (pid {pid})…")
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except ProcessLookupError:
                break
        PIDFILE.unlink(missing_ok=True)
        log("Killed.")
    else:
        log("No existing proxy running.")


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def proxy_is_healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def ensure_repo() -> None:
    if (PROXY_DIR / ".git").is_dir():
        log("Updating proxy repo…")
        old_rev = subprocess.run(
            ["git", "-C", str(PROXY_DIR), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        subprocess.run(["git", "-C", str(PROXY_DIR), "pull", "--ff-only", "-q"], check=False)
        new_rev = subprocess.run(
            ["git", "-C", str(PROXY_DIR), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        if old_rev != new_rev:
            DEPS_UPGRADED_MARKER.unlink(missing_ok=True)
    else:
        log("Cloning proxy repo…")
        PROXY_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", PROXY_REPO, str(PROXY_DIR)], check=True)

    # Patch ThinkingConfig to accept "adaptive" if not already patched.
    main_py = PROXY_DIR / "main.py"
    code = main_py.read_text()
    if '"adaptive"' not in code:
        code = code.replace(
            'Literal["enabled", "disabled"]',
            'Literal["enabled", "disabled", "adaptive"]',
        )
        main_py.write_text(code)

    if not DEPS_UPGRADED_MARKER.exists():
        log("Upgrading mlx-lm (one-time)…")
        subprocess.run(
            ["uv", "lock", "--upgrade-package", "mlx-lm"],
            cwd=str(PROXY_DIR),
            capture_output=True,
        )
        DEPS_UPGRADED_MARKER.touch()


def wait_for_healthy(port: int, timeout: int = 180) -> bool:
    deadline = time.monotonic() + timeout
    log(f"Waiting for proxy to be ready (loading model, up to {timeout}s)…")
    while time.monotonic() < deadline:
        if proxy_is_healthy(port):
            return True
        time.sleep(2)
    return False


def start_proxy(model: str, port: int) -> int:
    pid = read_pid()
    if pid and proxy_is_healthy(port):
        log(f"Proxy already running (pid {pid}), reusing.")
        return pid

    kill_existing()

    if port_in_use(port):
        log(f"ERROR: Port {port} is already in use by another process.")
        sys.exit(1)

    ensure_repo()

    # Derive a short display name from the model path.
    api_model_name = model.rsplit("/", 1)[-1].lower()

    env = {
        **os.environ,
        "HOST": "127.0.0.1",
        "PORT": str(port),
        "MODEL_NAME": model,
        "API_MODEL_NAME": api_model_name,
        "DEFAULT_MAX_TOKENS": "16384",
        "VERBOSE": "false",
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    log(f"Starting proxy on port {port} with {model}…")
    proc = subprocess.Popen(
        ["uv", "run", "--with", "transformers>=5.0", "main.py"],
        cwd=str(PROXY_DIR),
        env=env,
        stdout=open(LOGFILE, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    PIDFILE.write_text(str(proc.pid))
    log(f"Proxy started (pid {proc.pid}), log: {LOGFILE}")

    if not wait_for_healthy(port):
        log("ERROR: Proxy failed to become healthy. Check the log:")
        log(f"  cat {LOGFILE}")
        sys.exit(1)

    log("Proxy is ready.")
    return proc.pid


def start_claude(port: int, model: str, extra_args: list[str]) -> None:
    api_model_name = model.rsplit("/", 1)[-1].lower()
    env = {
        **os.environ,
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
        "ANTHROPIC_API_KEY": "local",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": api_model_name,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": api_model_name,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": api_model_name,
    }
    claude_bin = subprocess.run(
        ["which", "claude"], capture_output=True, text=True,
    ).stdout.strip()
    if not claude_bin:
        log("ERROR: 'claude' not found in PATH. Install it: https://docs.anthropic.com/en/docs/claude-code")
        sys.exit(1)

    log("Launching Claude Code…")
    os.execve(claude_bin, ["claude", "--bare"] + extra_args, env)


# ── CLI ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="claude-local",
        description="Run Claude Code against a local MLX model.",
    )
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        help=f"HuggingFace model ID (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Proxy port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Start proxy only, don't launch Claude Code",
    )
    parser.add_argument(
        "--kill",
        action="store_true",
        help="Kill running proxy and exit",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Force restart the proxy even if healthy",
    )

    args, extra = parser.parse_known_args()

    if args.kill:
        kill_existing()
        return

    if args.restart:
        kill_existing()

    start_proxy(args.model, args.port)

    if args.server:
        log(f"Proxy running at http://127.0.0.1:{args.port}")
        log(f"Run with: ANTHROPIC_BASE_URL=http://127.0.0.1:{args.port} claude")
        return

    start_claude(args.port, args.model, extra)


if __name__ == "__main__":
    main()
