# config_manager.py
import os
from dataclasses import dataclass, field
from typing import Any, Dict

from hydra import compose, initialize_config_dir
from hydra.core.config_store import ConfigStore
from omegaconf import OmegaConf

from flcode_pytorch.utils.configs import ServerConfig, ClientConfig


@dataclass
class GeneralConfig:
    exp_name: str = "exp1"
    log_path: str = "logs"
    data_path: str = "data"
    seed: int = 42
    zmq_ip_address: str = "localhost"
    zmq_port: int = 5555
    logging_level: str = "INFO"
    extra: Dict[str, Any] = field(default_factory=dict)


# --- Global config cache ---
_configs: Dict[str, Any] = {}
_namespace_map = {
    "general": ("general", GeneralConfig),
    "server": ("fl_server", ServerConfig),
    "client": ("fl_client", ClientConfig),
    "dataset": ("dataset", ClientConfig),
}


def setup_config(namespace: str):
    """Initialize and cache a config namespace (Hydra + dataclass)."""
    if namespace in _configs:
        return _configs[namespace]

    if namespace not in _namespace_map:
        raise ValueError(f"Unknown config namespace: {namespace}")

    config_name, dataclass_type = _namespace_map[namespace]
    cs = ConfigStore.instance()
    cs.store(name=namespace, node=dataclass_type)

    config_dir = os.path.join(os.getcwd(), "static", "config")
    with initialize_config_dir(config_dir=config_dir):
        overrides = []#sys.argv[1:]
        cfg = compose(config_name=config_name, overrides=overrides)

    config_dict = OmegaConf.to_container(cfg, resolve=True)
    _configs[namespace] = dataclass_type(**config_dict)
    return _configs[namespace]


def get_config(namespace: str):
    if namespace not in _configs:
        raise RuntimeError(f"Config '{namespace}' not configured. Call setup_config('{namespace}') first.")
    return _configs[namespace]
