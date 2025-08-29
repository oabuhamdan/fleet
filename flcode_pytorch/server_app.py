import flwr
import torch
from flwr.common import Context
from flwr.server import ServerApp, ServerAppComponents

from common.configs import *
from common.loggers import *
from flcode_pytorch.utils.contexts import ServerContext
from .my_client_manager import MyClientManager
from .my_server import MyServer
from .utils.model_utils import Net
from .utils.strategy_utils import get_strategy


def server_fn(context: Context):
    general_cfg: GeneralConfig = setup_config("general")
    server_cfg: ServerConfig = setup_config("server")

    log_file = Path(general_cfg.log_path) / "server.log"
    init_zmq("default", general_cfg.zmq_ip_address, general_cfg.zmq_port) if server_cfg.zmq_publish else None
    configure_logger("default", server_cfg.log_to_stream, log_file, general_cfg.logging_level)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    ctx = ServerContext(
        flwr_ctx=context,
        general_cfg=general_cfg,
        server_cfg=server_cfg,
        device=device
    )

    strategy = get_strategy(ctx, model=Net())
    client_manager = MyClientManager(ctx)
    config = flwr.server.ServerConfig(num_rounds=server_cfg.num_rounds)
    server = MyServer(ctx, client_manager=client_manager, strategy=strategy)

    return ServerAppComponents(server=server, config=config)


app = ServerApp(server_fn=server_fn)
