# config_manager.py
from dataclasses import dataclass, field
from typing import Any, Dict

from hydra import compose, initialize_config_dir
from hydra.core.config_store import ConfigStore
from omegaconf import OmegaConf

from flcode_pytorch.utils.configs import ServerConfig, ClientConfig


@dataclass
class GeneralConfig:
    exp_name: str = "exp1"
    log_path: str = "static/logs"
    data_path: str = "static/data"
    config_path: str = "static/config"
    seed: int = 42
    zmq_ip_address: str = "localhost"
    zmq_port: int = 5555
    logging_level: str = "INFO"
    extra: Dict[str, Any] = field(default_factory=dict)


# --- Global config cache ---
_configs: Dict[str, Any] = {}
cs = ConfigStore.instance()


def setup_config(config_path, config_name, dataclass_type, overrides=None):
    """Initialize and cache a config namespace (Hydra + dataclass)."""
    if config_name in _configs:
        return _configs[config_name]

    cs.store(name=config_name, node=dataclass_type)
    overrides = overrides or []
    with initialize_config_dir(config_dir=config_path, version_base="1.3"):
        yaml_cfg = compose(config_name=config_name, overrides=overrides)

    defaults = OmegaConf.structured(dataclass_type())
    merged = OmegaConf.merge(defaults, yaml_cfg)
    obj = OmegaConf.to_object(merged)
    _configs[config_name] = obj
    return obj


def get_config(namespace: str):
    if namespace not in _configs:
        raise RuntimeError(f"Config '{namespace}' not configured. Call setup_config('{namespace}') first.")
    return _configs[namespace]
