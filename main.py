from dataclasses import dataclass, field
from pathlib import Path

import hydra
from hydra.core.config_store import ConfigStore
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink  # always keep this import after OVSSwitch
from omegaconf import OmegaConf

from common.configs import FLServerConfig, FLClientConfig, BGConfig, SDNConfig, NetConfig, DatasetConfig
from common.dataset_utils import prepare_datasets
from common.loggers import configure_logger, info
from common.static import *
from common.utils import plot_topology
from containernet_code.background_traffic.background_gen import BGTrafficRunner
from containernet_code.background_traffic.traffic_generators import get_traffic_generator
from containernet_code.background_traffic.traffic_patterns import get_traffic_pattern
from containernet_code.experiment_runner import ExperimentRunner
from containernet_code.my_containernet import MyContainernet
from containernet_code.my_topology import TopologyHandler


@dataclass
class MainConfig:
    exp_name: str
    log_dir: str
    fl_server: FLServerConfig = field(default_factory=FLServerConfig)
    fl_client: FLClientConfig = field(default_factory=FLClientConfig)
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    net: NetConfig = field(default_factory=NetConfig)


cs = ConfigStore.instance()
cs.store(name="base_main", node=MainConfig)


@hydra.main(config_path=LOCAL_CONFIG_PATH, config_name="main", version_base="1.3")
def main(cfg: MainConfig):
    OmegaConf.save(cfg, LOCAL_RESOLVED_CONFIG_PATH)  # save resolved config for FL and BG containers
    log_path = Path(cfg.log_dir)
    configure_logger("default", log_to_stream=True, log_file=f"{log_path}/{cfg.exp_name}.log", level="INFO")

    prepare_datasets(cfg.dataset)
    controller = None
    if cfg.net.sdn.sdn_enabled:
        sdn_conf = cfg.net.sdn
        controller = RemoteController('c0', ip=sdn_conf.controller_ip, port=sdn_conf.controller_port)

    config_checks(cfg)
    topo_handler = TopologyHandler(log_path, cfg.net)
    plot_topology(log_path, topo_handler)

    background_traffic = None
    if cfg.net.bg.enabled:
        bg_conf = cfg.net.bg
        info("Background traffic generation is enabled.")
        bg_log_path = log_path / "bg_traffic"
        bg_log_path.mkdir(parents=True, exist_ok=True)
        pattern = get_traffic_pattern(bg_conf.rate_distribution, bg_conf.time_distribution)
        generator = get_traffic_generator(bg_conf.generator, bg_log_path, pattern=pattern)
        background_traffic = BGTrafficRunner(topo_handler.topo, generator, bg_log_path)

    experiment_runner = ExperimentRunner(log_path)
    net = MyContainernet(
        topo_handler=topo_handler, switch=OVSSwitch, link=TCLink, controller=controller,
        bg_runner=background_traffic, experiment_runner=experiment_runner
    )
    net.interact()
    info("FLEET terminated successfully.")


def config_checks(cfg):
    if not cfg.net.sdn.sdn_enabled and not cfg.net.topology.switch_config.get("stp", False):
        print("Warning: STP is disabled on switches, this may lead to loops in the network!")
        input("Proceed? (Enter to continue, Ctrl+C to abort)")
    if cfg.net.fl.server_limits and cfg.net.fl.server_limits.cpu < 0.5:
        print("Server CPU limit is set very low, this may lead to performance degradation.")
    if cfg.net.fl.server_limits and cfg.net.fl.server_limits.mem < 1024:
        print("Server memory limit is set very low, this may lead to instability.")
    if cfg.net.fl.clients_limits.cpu < 0.5:
        print("Client CPU limit is set very low, this may lead to performance degradation.")
    if cfg.net.fl.clients_limits.mem < 512:
        print("Client memory limit is set very low, this may lead to instability.")


if __name__ == "__main__":
    main()
