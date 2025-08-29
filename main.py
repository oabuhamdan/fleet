import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import hydra
from hydra.core.config_store import ConfigStore
from mininet.cli import CLI
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from omegaconf import OmegaConf

from common.configs import GeneralConfig
from common.loggers import configure_logger
from containernet_code.background_traffic.background_gen import BGTrafficRunner
from containernet_code.background_traffic.traffic_generators import BGTrafficGenerators
from containernet_code.background_traffic.traffic_patterns import BGTrafficPatterns
from containernet_code.config import NetConfig, SDNConfig, BGConfig
from containernet_code.experiment_runner import ExperimentRunner
from containernet_code.my_containernet import MyContainernet
from containernet_code.my_topology import MyTopology
from common.dataset_utils import prepare_datasets, DatasetConfig
from hydra.core.hydra_config import HydraConfig

@dataclass
class MainConfig:
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    sdn: SDNConfig = field(default_factory=SDNConfig)
    bg: BGConfig = field(default_factory=BGConfig)
    net: NetConfig = field(default_factory=NetConfig)
    general: GeneralConfig = field(default_factory=GeneralConfig)

cs = ConfigStore.instance()
cs.store(name="main", node=MainConfig)

@hydra.main(config_path="static/config", config_name="main", version_base="1.3")
def main(cfg: MainConfig):
    log_path = cfg.general.log_path
    configure_logger("default", log_file=f"{log_path}/net.log", level="INFO")
    prepare_datasets(cfg.dataset)

    controller = None
    if cfg.sdn.sdn_enabled:
        controller = RemoteController('c0', ip=cfg.sdn.controller_ip, port=cfg.sdn.controller_port)

    topo = MyTopology(cfg.general, cfg.net)
    background_traffic = None
    if cfg.bg.enabled:
        bg_log_path = Path(log_path) / "bg_traffic"
        bg_log_path.mkdir(parents=True, exist_ok=True)
        pattern = BGTrafficPatterns.create(cfg.bg.pattern_config)
        generator = BGTrafficGenerators.create(cfg.bg.generator_config, log_path=bg_log_path, pattern=pattern)
        background_traffic = BGTrafficRunner(topo, cfg.bg, generator, pattern, bg_log_path)

    experiment_runner = ExperimentRunner(log_path)
    net = MyContainernet(
        topo=topo, switch=OVSSwitch, link=TCLink, controller=controller,
        bg_runner=background_traffic, experiment_runner=experiment_runner
    )
    CLI(net)


if __name__ == "__main__":
    main()
