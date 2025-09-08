from typing import NamedTuple

import torch
from flwr.common import Context

from common.configs import *
from common.dataset_utils import DatasetConfig


class ServerContext(NamedTuple):
    flwr_ctx: Context
    server_cfg: ServerConfig
    dataset_cfg: DatasetConfig
    device: torch.device


class ClientContext(NamedTuple):
    simple_id: int
    flwr_ctx: Context
    client_cfg: ClientConfig
    dataset_cfg: DatasetConfig
    device: torch.device
