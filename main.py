from dataclasses import dataclass, field
from pathlib import Path

import hydra
from hydra.core.config_store import ConfigStore
from mininet.cli import CLI
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink  # always keep this import after OVSSwitch
from omegaconf import OmegaConf

from common.dataset_utils import prepare_datasets
from common.loggers import configure_logger
from common.static import *
from containernet_code.background_traffic.background_gen import BGTrafficRunner
from containernet_code.background_traffic.traffic_generators import BGTrafficGenerators
from containernet_code.background_traffic.traffic_patterns import BGTrafficPatterns
from containernet_code.experiment_runner import ExperimentRunner
from containernet_code.my_containernet import MyContainernet
from containernet_code.my_topology import TopologyHandler
from common.utils import plot_topology
from common.configs import FLServerConfig, FLClientConfig, BGConfig, SDNConfig, NetConfig, DatasetConfig


@dataclass
class MainConfig:
    exp_name: str
    log_dir: str
    fl_server: FLServerConfig = field(default_factory=FLServerConfig)
    fl_client: FLClientConfig = field(default_factory=FLClientConfig)
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    sdn: SDNConfig = field(default_factory=SDNConfig)
    bg: BGConfig = field(default_factory=BGConfig)
    net: NetConfig = field(default_factory=NetConfig)


cs = ConfigStore.instance()
cs.store(name="base_main", node=MainConfig)


@hydra.main(config_path=LOCAL_CONFIG_PATH, config_name="main", version_base="1.3")
def main(cfg: MainConfig):
    OmegaConf.save(cfg, LOCAL_RESOLVED_CONFIG_PATH)  # save resolved config for FL and BG containers
    log_path = Path(cfg.log_dir)
    configure_logger("default", log_to_stream=True, log_file=f"{log_path}/net.log", level="INFO")

    prepare_datasets(cfg.dataset)
    controller = None
    if cfg.sdn.sdn_enabled:
        controller = RemoteController('c0', ip=cfg.sdn.controller_ip, port=cfg.sdn.controller_port)

    topo_handler = TopologyHandler(log_path, cfg.net)
    plot_topology(log_path, topo_handler)

    background_traffic = None
    if cfg.bg.enabled:
        bg_log_path = log_path / "bg_traffic"
        bg_log_path.mkdir(parents=True, exist_ok=True)
        pattern = BGTrafficPatterns.create(cfg.bg.pattern_config)
        generator = BGTrafficGenerators.create(cfg.bg.generator_config, log_path=bg_log_path, pattern=pattern)
        background_traffic = BGTrafficRunner(topo_handler.topo, cfg.bg, generator, pattern, bg_log_path)

    experiment_runner = ExperimentRunner(log_path)
    net = MyContainernet(
        topo_handler=topo_handler, switch=OVSSwitch, link=TCLink, controller=controller,
        bg_runner=background_traffic, experiment_runner=experiment_runner
    )
    net.start()
    CLI(net)
    experiment_runner.stop_experiment()
    net.stop()
    print("Experiment finished successfully.")


if __name__ == "__main__":
    main()
