from mininet.node import Host
from mininet.net import Containernet

from containernet_code.background_traffic.background_gen import BGTrafficRunner
from containernet_code.experiment_runner import ExperimentRunner
from containernet_code.my_topology import MyTopology


class MyContainernet(Containernet):
    """Custom Mininet class for running"""

    def __init__(self, topo: MyTopology, experiment_runner: ExperimentRunner, bg_runner: BGTrafficRunner, **kwargs):
        Containernet.__init__(self, topo=topo, **kwargs)  # must be called first to initialize the Mininet base class
        self.background_traffic = bg_runner
        self.experiment_runner = experiment_runner
        self.fl_server_node = self.get(topo.fl_server)
        self.fl_client_nodes = [self.get(client) for client in topo.fl_clients]
        self.bg_client_nodes = {bg: self.get(bg) for bg in topo.bg_clients}
        self.background_traffic.setup_nodes(self.bg_client_nodes)
        self.experiment_runner.setup_nodes(self.fl_server_node, self.fl_client_nodes)

    def start_experiment(self, follow_logs=False, ping_fl_hosts=True, autostart_bg_traffic=True):
        """Start the experiment with background traffic and monitoring."""
        if ping_fl_hosts:
            print("Pinging FL hosts to ensure connectivity...")
            self.ping_fl_hosts()

        if autostart_bg_traffic:
            print("Starting background traffic generation...")
            self.background_traffic.start()

        print("Starting Experiment")
        self.experiment_runner.start_experiment()

        if follow_logs:
            print("Following logs...")
            self.follow_logs(self.fl_server_node)

    def follow_logs(self, client: Host, service: str = None):
        self.experiment_runner.follow_logs(client, service)

    def stop_experiment(self):
        """Stop the experiment and background traffic."""
        print("Stopping Experiment")
        self.experiment_runner.stop_experiment()
        self.background_traffic.stop()
        print("Experiment stopped successfully.")

    def ping_fl_hosts(self):
        for client in self.fl_client_nodes:
            result = self.fl_server_node.cmd(f"ping -c 1 {client.IP()}")
            if "1 received" in result:
                print(f"Ping successful from {self.fl_server_node.name} to {client.name}")
            else:
                print(f"Ping failed from {self.fl_server_node.name} to {client.name} ")

    def start_background_traffic(self):
        """Start background traffic generation."""
        print("Starting background traffic generation...")
        self.background_traffic.start()

    def stop_background_traffic(self):
        """Stop background traffic generation."""
        print("Stopping background traffic generation...")
        self.background_traffic.stop()

    def pause_experiment(self):
        """Pause the experiment."""
        print("Pausing Experiment")
        self.experiment_runner.pause_experiment()
        self.background_traffic.stop()
        print("Experiment paused successfully.")
