from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class TopologyConfig:
    """Topology configuration"""
    source: str = "topohub"
    topohub_id: Optional[str] = None
    custom_topology: Dict = field(default_factory=lambda: {"path": "", "class_name": ""})
    link_util_key: str = "deg"  # {deg, uni, org} for topohub, and user-defined for custom topologies
    link_config: Dict = field(default_factory=dict)
    switch_config: Dict = field(default_factory=lambda: {"failMode": "standalone", "stp": True})
    extra: Dict = field(default_factory=dict)


@dataclass
class FLClientConfig:
    """FL configuration"""
    clients_number: int = 10
    server_placement: str = "highest_degree"
    server_node_id: Optional[int] = None
    client_placement: str = "lowest_degree"
    image: str = "fl-app:latest"
    network: str = "10.0.0.0/16"
    clients_limits: Dict = field(default_factory=lambda: {"distribution": "homogeneous", "cpu": 0.5, "mem": 256})
    server_limits: Optional[Dict] = field(default_factory=lambda: {"cpu": 1, "mem": 2048})
    extra: Dict = field(default_factory=dict)


@dataclass
class BGConfig:
    """Background traffic configuration"""
    enabled: bool = False
    image: str = "bg-traffic:latest"
    network: str = "10.1.0.0/16"
    clients_limits: Dict = field(default_factory=lambda: {"cpu": 0.5, "mem": 256})
    generator_config: Dict = field(default_factory=lambda: {"name": "iperf"})
    pattern_config: Dict = field(default_factory=lambda: {"name": "poisson", "parallel_streams": 1,
                                                          "max_rate": 100.0, "min_rate": 1.0})
    extra: Dict = field(default_factory=dict)


@dataclass
class SDNConfig:
    """SDN configuration"""
    sdn_enabled: bool = False
    controller_ip: str = "localhost"
    controller_port: int = 6633
    controller_type: str = "openflow"
    extra: Dict = field(default_factory=dict)


@dataclass
class NetConfig:
    topology: TopologyConfig = field(default_factory=TopologyConfig)
    fl: FLClientConfig = field(default_factory=FLClientConfig)
    bg: BGConfig = field(default_factory=BGConfig)
    sdn: SDNConfig = field(default_factory=SDNConfig)