from typing import NamedTuple

import torch
from flwr.common import Context

from common.configs import *


class ServerContext(NamedTuple):
    flwr_ctx: Context
    general_cfg: GeneralConfig
    server_cfg: ServerConfig
    device: torch.device


class ClientContext(NamedTuple):
    simple_id: int
    flwr_ctx: Context
    general_cfg: GeneralConfig
    client_cfg: ClientConfig
    device: torch.device
