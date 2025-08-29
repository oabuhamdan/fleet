import ipaddress
import itertools
import random
from enum import Enum
from typing import Dict, List, Optional, Iterator, Any

import topohub.mininet
from mininet.node import Docker
from mininet.topo import Topo

from common.configs import GeneralConfig
from common.loggers import info
from containernet_code.config import NetConfig, TopologyConfig

# Constants
FL_SERVER_NAME = "flserver"
FL_NAME_FORMAT = "flc-{id}"
BG_NAME_FORMAT = "bgc-{switch}"


class TopoProcessor:
    """Base class for processing topologies."""
    NO_BG_WARNING = ("Warning: link {src} -> {dst} does not have a Link Utilization config."
                     "No BG traffic will run through it.")

    def __init__(self, cfg: TopologyConfig, *args, **kwargs):
        self.cfg = cfg
        self.args = args
        self.kwargs = kwargs

    def load_topology(self) -> None:
        """Load topology from file."""
        raise NotImplementedError("Subclasses must implement this method.")

    def get_processed_topology(self) -> Topo:
        """Process topology into nodes and links."""
        raise NotImplementedError("Subclasses must implement this method.")


class CustomTopoProcessor(TopoProcessor):
    """Processor for custom Mininet topology."""

    def __init__(self, cfg: TopologyConfig, *args, **kwargs):
        super().__init__(cfg, *args, **kwargs)
        self.path = cfg.custom_topology.get("path", "")
        self.class_name = cfg.custom_topology.get("class_name", "")
        self.topo: Optional[Topo] = None
        self.loaded = False
        if not self.path or not self.class_name:
            raise ValueError("Custom topology must specify 'path' and 'class_name'.")

    def load_topology(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("module", self.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        topo_class = getattr(module, self.class_name)
        self.topo = topo_class()
        self.loaded = True

    def get_processed_topology(self) -> Topo:
        """
        Process custom Mininet topology into nodes and links.
        The user is supposed to add all other details in the custom topology class.
        """
        if not self.loaded:
            self.load_topology()

        self.process_switches()
        self.process_links()
        return self.topo

    def process_switches(self):
        switches = self.topo.switches()
        for switch in switches:
            switch_info = self.topo.nodeInfo(switch)
            switch_info['degree'] = len(self.topo.g[switch])
            self.topo.setNodeInfo(
                name=switch.name,
                info=switch_info
            )

    def process_links(self):
        for link in self.topo.links():
            src, dst = link
            link_info = self.topo.linkInfo(src, dst)
            if self.cfg.link_util_key not in link_info:
                print(self.NO_BG_WARNING.format(src=src, dst=dst))

            link_util = link_info.pop(self.cfg.link_util_key, 0.0)
            link_info['util'] = dict(fwd=link_util, bwd=link_util)
            self.topo.setlinkInfo(
                src=src,
                dst=dst,
                info=link_info,
            )


class TopohubTopoProcessor(TopoProcessor):
    def __init__(self, cfg: TopologyConfig, *args, **kwargs) -> None:
        super().__init__(cfg, *args, **kwargs)
        self.topohub_id = cfg.topohub_id
        self.topo: Optional[Topo] = None
        self.loaded = False
        # if not self.topohub_id in topohub.mininet.TOPO_NAMED_CLS:
        #     raise ValueError(f"Invalid Topohub topology ID: {self.topohub_id} {topohub.mininet.TOPO_NAMED_CLS.keys()}")

    def load_topology(self) -> None:
        """Load TopoHub topology."""
        topo_cls = topohub.mininet.TOPO_NAMED_CLS[self.topohub_id]
        self.topo = topo_cls()
        self.loaded = True

    def get_processed_topology(self) -> Topo:
        """Process TopoHub topology into nodes and links."""
        if not self.loaded:
            self.load_topology()

        self.process_switches()
        self.process_links()
        return self.topo

    def process_switches(self):
        switches = self.topo.switches()
        switch_configs = self.cfg.switch_config
        for switch in switches:
            switch_info = self.topo.nodeInfo(switch)
            switch_info['degree'] = len(self.topo.g[switch])
            switch_info.update(switch_configs)  # Add switch-specific configurations
            self.topo.setNodeInfo(
                name=switch,
                info=switch_info
            )

    def process_links(self):
        link_configs = self.cfg.link_config
        for link in self.topo.links():
            src, dst = link
            link_info = self.topo.linkInfo(src, dst)
            link_info.update(link_configs)
            if self.cfg.link_util_key not in link_info["ecmp_fwd"]:
                print(self.NO_BG_WARNING.format(src=src, dst=dst))

            link_info['util'] = dict(
                fwd=link_info.pop("ecmp_fwd").get(self.cfg.link_util_key, 0.0),
                bwd=link_info.pop("ecmp_bwd").get(self.cfg.link_util_key, 0.0),
            )
            self.topo.setlinkInfo(
                src=src,
                dst=dst,
                info=link_info,
            )


class TopologyLoaders(Enum):
    """Enum for topology source types."""
    CUSTOM = CustomTopoProcessor
    TOPOHUB = TopohubTopoProcessor

    def init(self, *args, **kwargs):
        """Call the function associated with this strategy."""
        return self.value(*args, **kwargs)


def highest_degree(nodes, **kwargs):
    single = kwargs.get("single", False)
    return max(nodes, key=lambda n: nodes[n]['degree']) if single else sorted(nodes, key=lambda n: nodes[n]['degree'],
                                                                              reverse=True)


def lowest_degree(nodes, **kwargs):
    single = kwargs.get("single", False)
    return min(nodes, key=lambda n: nodes[n]['degree']) if single else sorted(nodes, key=lambda n: nodes[n]['degree'])


def random_nodes(nodes, **kwargs):
    single = kwargs.get("single", False)
    return random.choice(nodes) if single else random.sample(nodes, k=len(nodes))


def specific_node(nodes, **kwargs):
    node_id = kwargs.get("node_id")
    if node_id is None or node_id not in nodes:
        raise ValueError("specific_node strategy requires 'node_id'")
    return node_id


# --- Enum for strategy registry ---
class PlacementStrategy(Enum):
    HIGHEST_DEGREE = highest_degree
    LOWEST_DEGREE = lowest_degree
    RANDOM = random_nodes
    SPECIFIC_NODE = specific_node

    def apply(self, nodes, **kwargs):
        return self.value(nodes, **kwargs)


def random_pairs(config):
    """Generate infinite random CPU/memory pairs."""
    while True:
        cpu = random.uniform(config["cpu_min"], config["cpu_max"])
        mem = random.randint(config["mem_min"], config["mem_max"])
        yield cpu, mem


def stepped_pairs(config):
    """Generate infinite stepped CPU/memory pairs."""
    num_steps = config["num_steps"]

    if num_steps < 2:
        cpu, mem = config["cpu_min"], config["mem_min"]
        while True:
            yield cpu, mem
    else:
        cpu_step = (config["cpu_max"] - config["cpu_min"]) / (num_steps - 1)
        mem_step = (config["mem_max"] - config["mem_min"]) / (num_steps - 1)

        pairs = [
            (round(config["cpu_min"] + i * cpu_step, 3),
             int(config["mem_min"] + i * mem_step))
            for i in range(num_steps)
        ]
        yield from itertools.cycle(pairs)


def homogeneous_pairs(config):
    """Generate infinite homogeneous CPU/memory pairs."""
    cpu = config.get("cpu", 0.5)
    mem = config.get("mem", 256)
    while True:
        yield cpu, mem


class ClientLimitsGenerator(Enum):
    RANDOM = random_pairs
    STEPPED = stepped_pairs
    HOMOGENEOUS = homogeneous_pairs

    @classmethod
    def generator(cls, cfg, **kwargs) -> Iterator[Dict[str, Any]]:
        if not cfg: yield {}

        name = cfg.get("distribution", "homogeneous").upper()
        pair_generator = cls[name].value(**kwargs)

        for cpu, mem in pair_generator:
            yield {
                "mem_limit": f"{mem}m",
                "memswap_limit": f"{mem}m",
                "cpu_period": 100000,
                "cpu_quota": int(cpu * 100000),
            }


class MyTopology(Topo):
    """Mininet topology with enhanced topology handling."""

    def __init__(self, general_cfg: GeneralConfig,net_cfg: NetConfig, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.net_cfg = net_cfg
        self.general_cfg = general_cfg
        self.fl_server: Optional[str] = None
        self.fl_clients: List[str] = []
        self.bg_clients: List[str] = []
        self.topo = self._load_and_process_topology()
        self.build(topo_loaded=True)

    def _load_and_process_topology(self) -> Topo:
        """Load and process topology data based on configuration."""
        try:
            source = self.net_cfg.topology.source.upper()
            processor = TopologyLoaders[source].init(self.net_cfg.topology)
        except KeyError:
            raise ValueError(f"Invalid topology source name: {self.net_cfg.topology.source}")

        return processor.get_processed_topology()

    def build(self, *args, **params) -> None:
        """Build the complete network topology."""
        if not params.get("topo_loaded", False):
            return

        info("Building network topology...")
        fl_network_hosts = ipaddress.ip_network(self.net_cfg.fl.network).hosts()
        server_node_id = self._create_fl_server(fl_network_hosts)
        self._create_fl_clients(fl_network_hosts, server_node_id)

        if self.net_cfg.bg.enabled:
            if self.net_cfg.bg.network == self.net_cfg.fl.network:
                bg_network_hosts = fl_network_hosts  # continue from where FL clients left off
            else:
                bg_network_hosts = ipaddress.ip_network(self.net_cfg.bg.network).hosts()
            self._create_background_hosts(bg_network_hosts)

        print(f"Topology built: {len(self.topo.switches())} switches, {len(self.topo.links())} links")

    def _create_fl_server(self, fl_network_hosts) -> int:
        """Create FL server and connect it to the network."""
        nodes = self.topo.g.node.copy()
        placement = self.net_cfg.fl.server_placement.upper()
        server_specific = self.net_cfg.fl.server_node_id
        info("Available strategies:", list(PlacementStrategy.__members__.keys()))
        server_switch = PlacementStrategy[placement].apply(nodes, node_id=server_specific, single=True)

        server_limits = next(ClientLimitsGenerator.generator(self.net_cfg.fl.server_limits))
        ip = str(next(fl_network_hosts))  # assigns the first IP to the server
        self.fl_server = self.addHost(
            FL_SERVER_NAME,
            ip=ip,
            mac=self._ip_to_mac(ip),
            dimage=self.net_cfg.fl.image,
            **self._get_container_commons(self.general_cfg.data_path, self.general_cfg.log_path),
            **server_limits
        )

        self.addLink(self.fl_server, server_switch)
        info(f"FL server placed on node {server_switch}")
        return server_switch

    def _create_fl_clients(self, server_node_id, fl_network_hosts) -> None:
        """Create FL clients and connect them to the network."""
        nodes = self.topo.g.node.copy()
        nodes.pop(server_node_id)  # exclude server switch from client placement
        placement = self.net_cfg.fl.client_placement.upper()
        client_nodes = PlacementStrategy[placement].apply(self.topo.g.node)

        client_limits_generator = ClientLimitsGenerator.generator(self.net_cfg.fl.clients_limits)
        for i in range(1, self.net_cfg.fl.clients_number + 1):
            ip = str(next(fl_network_hosts))
            fl_client = self.addHost(
                FL_NAME_FORMAT.format(id=i),
                ip=ip, mac=self._ip_to_mac(ip),
                dimage=self.net_cfg.fl.image,
                **self._get_container_commons(self.general_cfg.data_path, self.general_cfg.log_path),
                **next(client_limits_generator)
            )

            client_switch = client_nodes[i % len(client_nodes)]
            self.addLink(fl_client, client_switch)
            self.fl_clients.append(fl_client)

        info(f"Created {len(self.fl_clients)} FL clients")

    def _create_background_hosts(self, bg_network_hosts) -> None:
        """Create background traffic hosts."""
        limits_generator = ClientLimitsGenerator.generator(self.net_cfg.bg.clients_limits)
        for switch in self.switches():
            ip = str(next(bg_network_hosts))
            bg_host = self.addHost(
                BG_NAME_FORMAT.format(switch=switch),
                ip=ip, mac=self._ip_to_mac(ip),
                dimage=self.net_cfg.bg.image,
                **self._get_container_commons(self.general_cfg.data_path, self.general_cfg.log_path),
                **next(limits_generator)
            )
            self.addLink(bg_host, switch)
            self.bg_clients.append(bg_host)

        info(f"Created {len(self.bg_clients)} background hosts")

    @staticmethod
    def _get_container_commons(data_path, logs_path) -> Dict:
        """Return containernet configuration parameters."""
        return {
            "volumes": [
                f"{data_path}:/app/data",
                f"{logs_path}:/app/logs"
            ],
            "sysctls": {"net.ipv4.tcp_congestion_control": "cubic"},
            "cls": Docker
        }

    @staticmethod
    def _ip_to_mac(ip: str) -> str:
        """Convert IPv4 string to MAC address format with leading zeros."""
        return ':'.join(f'{b:02x}' for b in [0, 0] + list(map(int, ip.split('.'))))
