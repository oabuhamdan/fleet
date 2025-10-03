from mininet.net import Containernet
from mininet.node import Host

from common.loggers import error, info
from containernet_code.background_traffic.background_gen import BGTrafficRunner
from containernet_code.experiment_runner import ExperimentRunner
from containernet_code.my_topology import TopologyHandler
import traceback


class MyContainernet(Containernet):
    """Custom Mininet class for running"""

    def __init__(self, topo_handler: TopologyHandler, experiment_runner: ExperimentRunner, bg_runner: BGTrafficRunner,
                 **kwargs):
        # must be called first to initialize the Mininet base class
        Containernet.__init__(self, topo=topo_handler.topo, **kwargs)
        self.bg_runner = bg_runner
        self.experiment_runner = experiment_runner
        self.fl_server_node = self.get(topo_handler.fl_server)
        self.fl_client_nodes = [self.get(client) for client in topo_handler.fl_clients]
        self.experiment_runner.setup_nodes(self.fl_server_node, self.fl_client_nodes)
        if bg_runner:
            self.bg_client_nodes = {bg: self.get(bg) for bg in topo_handler.bg_clients}
            self.bg_runner.setup_nodes(self.bg_client_nodes)

    def start_experiment(self, logs=False, ping=True, auto_bg=True):
        try:
            """Start the experiment with background traffic and monitoring."""
            if ping:
                info("Pinging FL hosts to ensure connectivity...")
                self.ping_fl_hosts()

            if self.bg_runner and auto_bg:
                info("Starting background traffic generation...")
                self.bg_runner.start()

            info("Starting Experiment")
            self.experiment_runner.start_experiment()

            if logs:
                print("Following logs...")
                self.follow_logs(self.fl_server_node)
        except Exception as e:
            error("Error during experiment start: {}\n{}".format(e, traceback.format_exc()))

    def follow_logs(self, client: Host, service: str = None):
        self.experiment_runner.follow_logs(client, service)

    def stop_experiment(self):
        """Stop the experiment and background traffic."""
        info("Stopping Experiment")
        self.experiment_runner.stop_experiment()
        if self.bg_runner:
            self.bg_runner.stop()
        info("Experiment stopped successfully.")

    def stop(self):
        self.stop_experiment()
        super().stop()

    def ping_fl_hosts(self):
        for client in self.fl_client_nodes:
            result = self.fl_server_node.cmd(f"ping -c 1 {client.IP()}")
            if "1 received" in result:
                print(f"Ping successful from {self.fl_server_node.name} to {client.name}")
            else:
                print(f"Ping failed from {self.fl_server_node.name} to {client.name} ")

    def start_background_traffic(self):
        """Start background traffic generation."""
        info("Starting background traffic generation...")
        self.bg_runner.start()

    def stop_background_traffic(self):
        """Stop background traffic generation."""
        info("Stopping background traffic generation...")
        self.bg_runner.stop()

    def pause_experiment(self):
        """Pause the experiment."""
        print("Pausing Experiment")
        self.experiment_runner.pause_experiment()
        self.bg_runner.stop()
        info("Experiment paused successfully.")
