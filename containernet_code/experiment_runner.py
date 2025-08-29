import shutil
import subprocess
from pathlib import Path
from typing import List, Dict


class ExperimentRunner:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.fl_server = None
        self.fl_clients = None
        self.running = False
        self.nodes_setup = False

        # Track processes per host: {host: {service_name: popen_obj}}
        self.processes: Dict[object, Dict[str, subprocess.Popen]] = {}
        self.last_service: Dict[object, str] = {}

    def setup_nodes(self, fl_server_node, fl_client_nodes):
        self.fl_server = fl_server_node
        self.fl_clients = fl_client_nodes
        self.nodes_setup = True

    def __enter__(self):
        print("Starting Experiment")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop_all()

        if exc_type:
            print(f"Experiment failed: {exc_type.__name__}: {exc_value}")
            if self.log_path.exists():
                shutil.rmtree(self.log_path)
        return True

    def start_experiment(self, overrides: str = None):
        if not self.nodes_setup:
            print("Nodes not set up. Call setup_nodes() before starting the experiment.")
            return

        if self.running:
            print("Experiment already running!")
            return

        self.running = True
        self._start_server(overrides)
        self._start_clients(overrides)
        print(f"Experiment started. Logs at: {self.log_path}")
        print("Use 'follow_logs(host, service)' to attach to output")

    def follow_logs(self, host, service: str = None):
        """Attach to logs of a host/service until Ctrl+C"""
        if service is None:
            service = self.last_service.get(host)

        if host not in self.processes or service not in self.processes[host]:
            print(f"No running process found for service={service} on host={host.name}")
            return

        p = self.processes[host][service]
        print(f"Following {host.name}:{service} (Ctrl+C to stop)")

        try:
            for line in iter(p.stdout.readline, ''):
                if not self.running or p.poll() is not None:
                    break
                if line:
                    print(line, end='')
        except KeyboardInterrupt:
            print(f"\nStopped following {service} on {host.name}")

    def stop_experiment(self):
        if not self.running:
            print("No experiment running")
            return
        self._stop_all()
        self.running = False
        print("Experiment stopped")

    def _start_server(self, overrides: str = None):
        super_link = self.fl_server.popen("venv/bin/flower-superlink --insecure")
        self._register_process(self.fl_server, "flower-superlink", super_link)

    def _start_clients(self, overrides: str = None):
        server_ip = self.fl_server.IP()
        cmd = f"venv/bin/flower-supernode --insecure --superlink='{server_ip}:9092' --node-config='cid={{id}}'"

        for i, client in enumerate(self.fl_clients, 1):
            supernode = client.popen(cmd.format(id=i))
            self._register_process(client, "flower-supernode", supernode)

        print(f"Started {len(self.fl_clients)} clients")

    def _start_app(self):
        server_ip = self.fl_server.IP()
        cmd = ["flwr", "run", "--federation-config", f"address={server_ip}:9093"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"{result.stdout}") if result.returncode == 0 else print(f"{result.stderr}")

    def wait_for_completion(self):
        if not self.running:
            print("No experiment running")
            return

        print("Waiting for server completion...")
        try:
            server_proc = self.processes[self.fl_server].get("flwr-serverapp")
            if server_proc:
                server_proc.wait()
            self.stop_experiment()
        except KeyboardInterrupt:
            print("\nInterrupted. Use 'stop_experiment()' to stop manually.")

    def _stop_all(self):
        for host, procs in self.processes.items():
            for svc, p in procs.items():
                if p.poll() is None:
                    p.terminate()
        self.processes.clear()
        self.last_service.clear()

    def _register_process(self, host, service, popen_obj):
        if host not in self.processes:
            self.processes[host] = {}
        self.processes[host][service] = popen_obj
        self.last_service[host] = service

    def pause_experiment(self):
        pass
