import flwr
import torch
from flwr.common import Context
from flwr.server import ServerApp, ServerAppComponents

from common.configs import *
from common.dataset_utils import DatasetConfig
from common.loggers import *
from flcode_pytorch.utils.contexts import ServerContext
from .my_client_manager import MyClientManager
from .my_server import MyServer
from .utils.model_utils import Net
from common.static import CONTAINER_LOG_PATH, CONTAINER_CONFIG_PATH
from .utils.strategy_utils import get_strategy


def server_fn(context: Context):
    server_cfg: ServerConfig = setup_config(CONTAINER_CONFIG_PATH, "server", ServerConfig)
    dataset_cfg: DatasetConfig = setup_config(CONTAINER_CONFIG_PATH, "dataset", DatasetConfig)
    log_file = Path(CONTAINER_LOG_PATH) / "server.log"
    if server_cfg.zmq["enable"]:
        zmq_ip_address = server_cfg.zmq["host"]
        zmq_port = server_cfg.zmq["port"]
        init_zmq("default", zmq_ip_address, zmq_port)
    configure_logger("default", server_cfg.log_to_stream, log_file, server_cfg.logging_level)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    ctx = ServerContext(
        flwr_ctx=context,
        server_cfg=server_cfg,
        dataset_cfg=dataset_cfg,
        device=device
    )

    strategy = get_strategy(ctx, model=Net())
    print(f"Using strategy: {strategy}")
    client_manager = MyClientManager(ctx)
    config = flwr.server.ServerConfig(num_rounds=server_cfg.num_rounds)
    server = MyServer(ctx, client_manager=client_manager, strategy=strategy)

    return ServerAppComponents(server=server, config=config)


app = ServerApp(server_fn=server_fn)
