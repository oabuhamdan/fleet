from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ServerConfig:
    log_to_stream: bool = True
    strategy: str = "FedAvg"
    min_fit_clients: int = 1
    min_evaluate_clients: int = min_fit_clients
    min_available_clients: int = min_fit_clients
    num_rounds: int = 10
    fraction_fit: float = 1
    fraction_evaluate: float = 1
    server_evaluation: bool = False
    val_batch_size: int = 128
    server_param_init: bool = True
    stop_by_accuracy: bool = False
    accuracy_level: float = 0.8
    collect_metrics: bool = False
    collect_metrics_interval: int = 60
    zmq_publish: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClientConfig:
    log_to_stream: bool = True
    train_batch_size: int = 32
    val_batch_size: int = 128
    local_epochs: int = 1
    learning_rate: float = 1e-3
    log_interval: int = 100
    collect_metrics: bool = True
    collect_metrics_interval: int = 5
    server_address: str = "tcp://localhost:5555"
    zmq_publish: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)
