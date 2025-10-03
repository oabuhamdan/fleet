import re
import shutil
import subprocess
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from mininet.node import Host

from common.loggers import error, warning, info, debug


class ExperimentRunner:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.fl_server = None
        self.fl_clients = None
        self.running = False
        self.nodes_setup = False
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        # Track running services: {host: [service_names]}
        self.running_services: Dict[Host, List[tuple[str, int]]] = defaultdict(list)

    def setup_nodes(self, fl_server_node, fl_client_nodes):
        if self.nodes_setup: return
        self.fl_server = fl_server_node
        self.fl_clients = fl_client_nodes
        self.nodes_setup = True

    def start_experiment(self):
        if not self.nodes_setup:
            error("Nodes not set up. Call setup_nodes() before starting.")
            return
        if self.running:
            warning("Experiment already running!")
            return

        self.running = True
        self._start_server()
        time.sleep(2)
        self._start_clients()
        time.sleep(2)
        self._start_app()
        self._start_serverapp_monitor()
        info(f"Experiment started. Logs at: {self.log_path}")

    def follow_logs(self, host, service: str = None):
        service = service or self._get_last_service(host)[0]
        pid = next((pid for name, pid in self.running_services[host] if name == service), None)
        if not pid:
            print(f"No running service '{service}' found on {host.name}")
            return

        log_file = f"/tmp/{service}.log"
        print(f"Following {host.name}:{service} logs (Ctrl+C to stop)")

        try:
            proc = host.popen(["tail", "-f", f"--pid={pid}", log_file], stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                print(line, end='')

        except KeyboardInterrupt:
            proc.terminate()
            host.pexec(["pkill", "-f", f"tail -f {log_file}"])
            print(f"\nStopped following {service} on {host.name}")

    def stop_experiment(self):
        if not self.running:
            debug("No experiment running")
            return
        self.running = False
        self._stop_all()
        info("Experiment stopped")

    def _stop_all(self):
        """Stop all services on all hosts"""
        for host, services in self.running_services.items():
            for service_name, pid in services:
                host.pexec(["kill", "-9", str(pid)])
                debug(f"Stopped {service_name} on {host.name}")
        self.running_services.clear()

    def get_status(self):
        if not self.running:
            debug("No experiment running")
            return

        print("Experiment Status:")
        for host, services in self.running_services.items():
            print(f"{host.name}:")
            for service_name, pid in services:
                status = "Running" if self._is_running(host, pid) else "Not Running"
                print(f"  - {service_name} - {status}")

    def _is_running(self, host, pid):
        # f"kill -0 {pid} && echo 'RUNNING' || echo 'STOPPED'"
        _, _, exitcode = host.pexec(["ps", "-p", str(pid)])
        return exitcode == 0

    def _start_server(self):
        cmd = f"venv/bin/flower-superlink --insecure --isolation process"
        self._start_service(self.fl_server, cmd, "flower-superlink")
        cmd = f"venv/bin/flwr-serverapp --insecure --run-once"
        self._start_service(self.fl_server, cmd, "flwr-serverapp")

    def _start_clients(self):
        server_ip = self.fl_server.IP()
        cmd1 = f"venv/bin/flower-supernode --insecure --isolation process  --superlink={server_ip}:9092 --node-config=cid={{i}}"
        cmd2 = f"venv/bin/flwr-clientapp --insecure"
        for i, client in enumerate(self.fl_clients, 1):
            self._start_service(client, cmd1.format(i=i), "flower-supernode")
            self._start_service(client, cmd2, "flwr-clientapp")

        info(f"Started {len(self.fl_clients)} clients")

    def _start_app(self):
        server_bridge_ip = self.fl_server.dcinfo['NetworkSettings']['Networks']['bridge']['IPAddress']
        cmd = [".venv/bin/flwr", "run", "--federation-config", f"address='{server_bridge_ip}:9093'"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            error(f"{result.stderr}")
            raise RuntimeError("Failed to start flwr app")

    def _start_service(self, host, cmd, name):
        full_cmd = f"nohup {cmd} > /tmp/{name}.log 2>&1 & "
        host.cmd(full_cmd)
        pid, _, _ = host.pexec(["pgrep", "-f", name])
        debug(f"Started {name} on {host.name} with PID {pid.strip()}")
        self.running_services[host].append((name, int(pid)))

    def _start_serverapp_monitor(self):
        def _monitor_serverapp():
            """Background thread to monitor serverapp completion"""
            while self.running:
                pid = self._get_last_service(self.fl_server)[1]
                if not self._is_running(self.fl_server, pid):
                    info("flwr-serverapp completed. Stopping experiment...")
                    self.stop_experiment()
                    break
                time.sleep(5)  # Check every 5 seconds

        """Monitor flwr-serverapp and auto-stop experiment when it completes"""
        threading.Thread(target=_monitor_serverapp, daemon=True).start()

    def _get_last_service(self, host):
        """Get the last (most recent) service for a host"""
        services = self.running_services.get(host, [])
        name, pid = services[-1] if services else (None, None)
        return name, pid

    def _clean_output(self, text, strip=True, compress=False):
        text = self.ansi_escape.sub('', text)
        if strip:
            text = '\n'.join(line.strip() for line in text.splitlines())
        if compress:
            text = re.sub(r'\s+', ' ', text)
        return text
