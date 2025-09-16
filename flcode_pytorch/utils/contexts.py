from typing import NamedTuple

import torch
from flwr.common import Context

from common.configs import FLServerConfig, FLClientConfig, DatasetConfig


class ServerContext(NamedTuple):
    flwr_ctx: Context
    server_cfg: FLServerConfig
    dataset_cfg: DatasetConfig
    device: torch.device


class ClientContext(NamedTuple):
    simple_id: int
    flwr_ctx: Context
    client_cfg: FLClientConfig
    dataset_cfg: DatasetConfig
    device: torch.device
