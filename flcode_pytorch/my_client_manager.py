from dataclasses import dataclass
from typing import Optional, Any, ClassVar

from apscheduler.schedulers.background import BackgroundScheduler
from flwr.common import GetPropertiesIns
from flwr.server import SimpleClientManager
from flwr.server.client_proxy import ClientProxy
from flwr.server.criterion import Criterion

from common.loggers import debug
from flcode_pytorch.utils.contexts import ServerContext


@dataclass
class ClientProps:
    cid: str = ""
    system: dict = None
    metrics: dict = None
    dataset: dict = None

    PROPS_MAP: ClassVar[dict[str, str]] = {
        "system": "system",
        "metrics": "metrics",
        "dataset": "dataset"
    }

    def update_property(self, props_type: str, value: Any) -> None:
        if props_type in self.PROPS_MAP:
            setattr(self, self.PROPS_MAP[props_type], value)


class MyClientManager(SimpleClientManager):
    def __init__(self, ctx: ServerContext, criterion: Optional[Criterion] = None) -> None:
        super().__init__()
        self.ctx = ctx
        self.clients_info: dict[str, ClientProps] = {}
        self.criterion = criterion
        self.scheduler: Optional[BackgroundScheduler] = None
        if self.ctx.server_cfg.collect_metrics:
            self.scheduler = BackgroundScheduler()
            self.scheduler.start()

    def register(self, client: ClientProxy) -> bool:
        debug(f"Registering client {client.cid}")
        success = super().register(client)
        self.setup_client_info(client)
        return success

    def unregister(self, client: ClientProxy) -> None:
        """Unregister a client and remove its information."""
        super().unregister(client)
        if client.cid in self.clients_info:
            del self.clients_info[client.cid]
            debug(f"Unregistered client {client.cid} and removed its information.")
            if self.scheduler:
                self.scheduler.remove_job(f"metrics-{client.cid}")

    def local_get_client_info(self, client: ClientProxy) -> ClientProps:  # Changed return type
        """Get information about a specific client."""
        return self.clients_info.get(client.cid, None)

    def setup_client_info(self, client: ClientProxy):
        # Initialize the ClientProps for this client if it doesn't exist
        if client.cid not in self.clients_info:
            self.clients_info[client.cid] = ClientProps(cid=client.cid)
            self.remote_client_props(client, "system")
            if self.ctx.server_cfg.collect_metrics:
                interval = self.ctx.server_cfg.collect_metrics_interval
                self.scheduler.add_job(lambda c=client: self.remote_client_props(c, "metrics"), "interval",
                                       seconds=interval, id=f"metrics-{client.cid}", replace_existing=True)

    def remote_client_props(self, client, props_type):
        properties = client.get_properties(GetPropertiesIns({"props_type": props_type}), None, None).properties
        props_dict = dict(properties)
        self.clients_info[client.cid].update_property(props_type, props_dict)
