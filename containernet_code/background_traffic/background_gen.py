from typing import Dict

from mininet.node import Host
from mininet.topo import Topo

from common.loggers import info
from common.static import BG_NAME_FORMAT
from .traffic_generators import TrafficGenerator
from .traffic_patterns import TrafficPattern
from ..config import BGConfig


# Main BGTrafficGenerator Class
class BGTrafficRunner:
    """Modular background traffic generator."""

    def __init__(self, topo: Topo, cfg: BGConfig, generator: TrafficGenerator, pattern: TrafficPattern, log_path):
        self.cfg = cfg
        self.topo = topo
        self.generator = generator
        self.pattern = pattern
        self.log_path = log_path
        self.nodes_setup = False

        self.bg_clients: Dict[str, Host] = {}

    def setup_nodes(self, bg_client_nodes: Dict[str, Host]):
        """Setup BG client nodes."""
        self.bg_clients = bg_client_nodes
        self.nodes_setup = True

    def start(self) -> None:
        """Start traffic generation and monitoring."""
        # Create flows for each link
        if not self.nodes_setup:
            info("No BG clients available for traffic generation. Try calling setup_nodes() first.")
            return

        flow_id_format = "{src}_{dst}"
        for src, dst, link_info in self.topo.links(withInfo=True):
            src_bg = self.bg_clients[BG_NAME_FORMAT.format(switch=src)]
            dst_bg = self.bg_clients[BG_NAME_FORMAT.format(switch=dst)]

            # Forward flow
            flow_id = flow_id_format.format(src=src_bg.name, dst=dst_bg.name)
            fwd_util = link_info["util"].get("fwd", 0)
            self.generator.start_flow(src_bg, dst_bg, fwd_util, flow_id)

            # Backward flow
            bwd_util = link_info["util"].get("bwd", 0)
            flow_id = flow_id_format.format(src=dst_bg.name, dst=src_bg.name)
            self.generator.start_flow(dst_bg, src_bg, bwd_util, flow_id)

        self._start_monitoring()

    def stop(self) -> None:
        """Stop all traffic and monitoring."""
        self.generator.stop_flows(list(self.bg_clients.values()))

        # Stop monitoring
        for bg_client in self.bg_clients.values():
            bg_client.cmd("pkill -f 'network_stats.sh'")

        info("Traffic generation stopped")

    def _start_monitoring(self) -> None:
        """Start network monitoring for all BG hosts."""
        pass
        # for bg_client in self.bg_clients:
        #     interface = bg_client.defaultIntf()
        #     log_file = self.log_path / f"{bg_client}_network.csv"
        #     bg_client.cmd(f"./network_stats.sh {interface} 10 {log_file} > /dev/null 2>&1 &")
