from dataclasses import dataclass, field
from pathlib import Path

import hydra
from hydra.core.config_store import ConfigStore
from mininet.cli import CLI
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink  # always keep this import after OVSSwitch

from common.configs import GeneralConfig
from common.dataset_utils import prepare_datasets, DatasetConfig
from common.loggers import configure_logger
from containernet_code.background_traffic.background_gen import BGTrafficRunner
from containernet_code.background_traffic.traffic_generators import BGTrafficGenerators
from containernet_code.background_traffic.traffic_patterns import BGTrafficPatterns
from containernet_code.config import NetConfig, SDNConfig, BGConfig
from containernet_code.experiment_runner import ExperimentRunner
from containernet_code.my_containernet import MyContainernet
from containernet_code.my_topology import TopologyHandler
from containernet_code.utils import plot_topology


@dataclass
class MainConfig:
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    sdn: SDNConfig = field(default_factory=SDNConfig)
    bg: BGConfig = field(default_factory=BGConfig)
    net: NetConfig = field(default_factory=NetConfig)
    general: GeneralConfig = field(default_factory=GeneralConfig)


cs = ConfigStore.instance()
cs.store(name="base_main", node=MainConfig)


@hydra.main(config_path="static/config", config_name="main", version_base="1.3")
def main(cfg: MainConfig):
    log_path = Path(cfg.general.log_path)
    configure_logger("default", log_to_stream=False, log_file=f"{log_path}/net.log", level="INFO")

    prepare_datasets(cfg.dataset)

    controller = None
    if cfg.sdn.sdn_enabled:
        controller = RemoteController('c0', ip=cfg.sdn.controller_ip, port=cfg.sdn.controller_port)

    topo_handler = TopologyHandler(cfg.general, cfg.net)
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
