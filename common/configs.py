from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from omegaconf import OmegaConf


@dataclass
class DatasetConfig:
    path: str = "static/data"
    name: str = "cifar10"
    partitioner_cls_name: str = "IidPartitioner"
    partitioner_kwargs: dict = field(default_factory=dict)
    force_create: bool = False
    test_size: float = 0.2
    server_eval: bool = True
    train_split_key: str = "train"
    test_split_key: str = "test"


@dataclass
class FLServerConfig:
    log_to_stream: bool = True
    logging_level: str = "INFO"
    strategy: str = "FedAvg"
    min_fit_clients: int = 1
    min_evaluate_clients: int = min_fit_clients
    min_available_clients: int = min_fit_clients
    num_rounds: int = 1
    fraction_fit: float = 1
    fraction_evaluate: float = 1
    server_eval: bool = False
    val_batch_size: int = 128
    server_param_init: bool = True
    stop_by_accuracy: bool = False
    accuracy_level: float = 0.8
    collect_metrics: bool = False
    collect_metrics_interval: int = 60
    zmq: Dict[str, Any] = field(default_factory=lambda: {"enable": False, "host": "localhost", "port": 5555})
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FLClientConfig:
    log_to_stream: bool = True
    logging_level: str = "INFO"
    train_batch_size: int = 32
    val_batch_size: int = 128
    local_epochs: int = 1
    learning_rate: float = 1e-3
    log_interval: int = 100
    collect_metrics: bool = False
    collect_metrics_interval: int = 5
    server_address: str = "tcp://localhost:5555"
    zmq: Dict[str, Any] = field(default_factory=lambda: {"enable": False, "host": "localhost", "port": 5555})
    extra: Dict[str, Any] = field(default_factory=dict)


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
class ContainernetHostConfig:
    """FL configuration"""
    clients_number: int = 10
    server_placement: Dict = field(default_factory=lambda: {"name": "highest_degree"})
    client_placement: Dict = field(default_factory=lambda: {"name": "lowest_degree"})
    image: str = "fl-app:latest"
    network: str = "10.0.0.0/16"
    clients_limits: Dict = field(default_factory=lambda: {"distribution": "homogeneous", "cpu": 0.7, "mem": 1024})
    server_limits: Optional[Dict] = field(default_factory=lambda: {"cpu": 1, "mem": 4096})
    extra: Dict = field(default_factory=dict)


@dataclass
class BGConfig:
    """Background traffic configuration"""
    enabled: bool = False
    image: str = "bg-traffic:latest"
    network: str = "10.1.0.0/16"
    clients_limits: Dict = field(default_factory=lambda: {"cpu": 0.5, "mem": 256})
    rate_distribution: Dict = field(default_factory=lambda: {"name": "poisson", "parallel_streams": 1})
    time_distribution: Dict = field(default_factory=lambda: {"name": "poisson"})
    generator: Dict = field(default_factory=lambda: {"name": "iperf"})
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
    fl: ContainernetHostConfig = field(default_factory=ContainernetHostConfig)
    bg: BGConfig = field(default_factory=BGConfig)
    sdn: SDNConfig = field(default_factory=SDNConfig)


def get_configs_from_file(path, configs_name, data_class_type):
    cfg = OmegaConf.load(path)
    cfg = OmegaConf.to_container(getattr(cfg, configs_name), resolve=True)
    cfg = OmegaConf.merge(data_class_type(), cfg)
    return cfg
