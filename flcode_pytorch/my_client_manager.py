from collections import deque
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
from threading import Thread
from typing import Optional

from flwr.common import GetPropertiesIns
from flwr.server import SimpleClientManager
from flwr.server.client_proxy import ClientProxy
from flwr.server.criterion import Criterion

from common.loggers import debug
from flcode_pytorch.utils.contexts import ServerContext


@dataclass
class ClientProps:
    cid: str
    system: dict = field(default_factory=dict)
    dataset: dict = field(default_factory=dict)
    metrics: deque = field(default_factory=lambda: deque(maxlen=10))


class MyClientManager(SimpleClientManager):
    def __init__(self, ctx: ServerContext, criterion: Optional[Criterion] = None) -> None:
        super().__init__()
        self.ctx = ctx
        self.clients_info: dict[str, ClientProps] = {}
        self.criterion = criterion

    def register(self, client: ClientProxy) -> bool:
        debug(f"Registering client {client.cid}")
        success = super().register(client)
        # Use threading to avoid blocking
        Thread(target=self.setup_client_info, args=(client,), daemon=True).start()
        return success

    def setup_client_info(self, client: ClientProxy):
        # Initialize the ClientProps for this client if it doesn't exist
        if client.cid not in self.clients_info:
            self.clients_info[client.cid] = ClientProps(cid=client.cid)
            info = self._remote_client_props(client, "system,dataset")
            self.clients_info[client.cid].system = info.get("system", {})
            self.clients_info[client.cid].dataset = info.get("dataset", {})

    def unregister(self, client: ClientProxy) -> None:
        """Unregister a client and remove its information."""
        super().unregister(client)
        if client.cid in self.clients_info:
            del self.clients_info[client.cid]
            debug(f"Unregistered client {client.cid} and removed its information.")

    def local_get_client_info(self, client: ClientProxy) -> Optional[ClientProps]:  # Changed return type
        """Get information about a specific client."""
        props = self.clients_info.get(client.cid, None)
        return deepcopy(props) if props else None

    def collect_client_metrics(self, client: ClientProxy):
        client_props = self.clients_info[client.cid]
        new_metrics = self._remote_client_props(client, "metrics")
        client_props.metrics.append(new_metrics)

    @staticmethod
    def _remote_client_props(client, props_type):
        properties = client.get_properties(GetPropertiesIns({"props_type": props_type}), None, None).properties
        props_dict = dict(properties)
        return props_dict

    def sample(
            self,
            num_clients: int,
            min_num_clients: Optional[int] = None,
            criterion: Optional[Criterion] = None,
    ) -> list[ClientProxy]:
        clients = super().sample(num_clients, min_num_clients, criterion)
        if self.ctx.server_cfg.collect_metrics:
            with ThreadPoolExecutor(max_workers=len(clients)) as executor:
                executor.map(self.collect_client_metrics, clients)
        return clients
