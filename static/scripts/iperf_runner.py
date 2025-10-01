#!/usr/bin/env python3
import os, sys, signal, json, subprocess, socket, time
from pathlib import Path
from datetime import datetime

BASE_LOG_PATH = Path("log/bg_traffic")
STATE_DIR = Path("/tmp")


# --- Helpers ---
def state_file(sid, role):
    return STATE_DIR / f"iperf_state_{sid}_{role}.json"


def load_state(sid, role):
    f = state_file(sid, role)
    return json.loads(f.read_text()) if f.exists() else {}


def save_state(sid, role, state):
    state_file(sid, role).write_text(json.dumps(state, indent=2))


def log(msg, fh=None):
    line = f"[{datetime.now():%F %T}] {msg}"
    if fh:
        fh.write(line + "\n")
        fh.flush()


def wait_for_server(host, port, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"❌ Timed out waiting for server {host}:{port}")


def load_rates(sid):
    f = Path("/tmp") / f"rates_{sid}.txt"
    if not f.exists():
        sys.exit("❌ rates file missing")
    lines = [l.strip() for l in f.read_text().splitlines() if l.strip()]
    rates = [int(float(x)) for x in lines[0].split(",")]
    durations = [int(float(x)) for x in lines[1].split(",")]
    return list(zip(rates, durations))


# --- Server ---
def run_server(sid, port):
    log_fh = open(BASE_LOG_PATH / f"iperf_log_{sid}.txt", "a")
    log(f"📡 Starting iperf3 server on port {port}", log_fh)

    proc = subprocess.Popen(["iperf3", "-s", "-i", "10", "-p", str(port)])
    save_state(sid, "server", {"pid": proc.pid, "port": port})

    proc.wait()
    if proc.returncode != 0:
        log(f"❌ Server exited with code {proc.returncode}", log_fh)
        sys.exit(proc.returncode)


# --- Client ---
def run_client(sid, dst, port, parallel):
    steps = load_rates(sid)
    log_fh = open(BASE_LOG_PATH / f"iperf_log_{sid}.txt", "a")
    log(f"🚀 Starting iperf3 client → {dst}:{port}", log_fh)

    wait_for_server(dst, port)
    state = load_state(sid, "client")
    step_idx = state.get("step", 0)

    while not state.get("paused", False):
        rate, dur = steps[step_idx % len(steps)]
        log(f"Step {step_idx}: {rate} Mbps for {dur}s", log_fh)

        proc = subprocess.Popen([
            "iperf3", "-c", dst, "-p", str(port),
            "-t", str(dur), "-b", f"{rate}M",
            "-P", str(parallel)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # ✅ Only update what changed
        state["pid"] = proc.pid
        state["step"] = step_idx
        save_state(sid, "client", state)

        out, err = proc.communicate()
        if proc.returncode != 0:
            log(f"❌ Client error {proc.returncode}: {err}", log_fh)

        step_idx += 1
        state = load_state(sid, "client")


# --- Control ---
def do_pause(sid):
    st = load_state(sid, "client")
    pid = st.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    st["paused"] = True
    st["pid"] = None
    save_state(sid, "client", st)
    print(f"✅ Paused {sid}")


def do_resume(sid):
    st = load_state(sid, "client")
    if not st.get("dst"):
        sys.exit("❌ No previous client state")
    st["paused"] = False
    save_state(sid, "client", st)
    run_client(sid, st["dst"], st["port"], st["parallel"])


def do_stop(sid, role):
    st = load_state(sid, role)
    pid = st.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    f = state_file(sid, role)
    if f.exists(): f.unlink()
    print(f"✅ Stopped {role} for {sid}")


def show_status(sid):
    s = {}
    for role in ["client", "server"]:
        f = state_file(sid, role)
        if f.exists():
            s[role] = load_state(sid, role)
    print(json.dumps(s, indent=2))


# --- CLI ---
def usage():
    print("Usage:")
    print("  server <sid> <port>")
    print("  client <sid> <dst> <port> <parallel>")
    print("  pause <sid>")
    print("  resume <sid>")
    print("  stop <sid> <client|server>")
    print("  status <sid>")


if __name__ == "__main__":
    if len(sys.argv) < 3: usage(); sys.exit(1)
    cmd, sid = sys.argv[1], sys.argv[2]

    if cmd == "server":
        run_server(sid, int(sys.argv[3]))
    elif cmd == "client":
        run_client(sid, sys.argv[3], int(sys.argv[4]), int(sys.argv[5]))
    elif cmd == "pause":
        do_pause(sid)
    elif cmd == "resume":
        do_resume(sid)
    elif cmd == "stop":
        if len(sys.argv) < 4: usage(); sys.exit(1)
        do_stop(sid, sys.argv[3])
    elif cmd == "status":
        show_status(sid)
    else:
        usage()
        sys.exit(1)
