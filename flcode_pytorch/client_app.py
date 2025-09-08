"""pytorchexample: A Flower / PyTorch app."""
import time
from collections import OrderedDict
from pathlib import Path

import torch
from flwr.client import ClientApp, NumPyClient
from flwr.common import Context, Config, Scalar

from common.configs import setup_config
from common.dataset_utils import get_dataloader, DatasetConfig
from common.loggers import init_zmq, configure_logger, info, debug, warning, to_zmq
from common.static import CONTAINER_LOG_PATH, CONTAINER_CONFIG_PATH, CONTAINER_DATA_PATH
from .utils import client_metrics_utils
from .utils.client_metrics_utils import MetricsCollector
from .utils.configs import ClientConfig
from .utils.contexts import ClientContext
from .utils.model_utils import Net, get_weights, set_weights, test, train


class FlowerClient(NumPyClient):
    def __init__(self, ctx: ClientContext, net, trainloader, valloader, metrics_collector):
        self.ctx = ctx
        self.net = net
        self.trainloader = trainloader
        self.valloader = valloader
        self.metrics_collector: MetricsCollector = metrics_collector

    def fit(self, parameters, config):
        # we can add batch size an quantization bits to config if needed
        local_epochs = config.get("local_epochs", self.ctx.client_cfg.local_epochs)
        learning_rate = config.get("learning_rate", self.ctx.client_cfg.learning_rate)

        set_weights(self.net, parameters)
        tik = time.perf_counter()
        optim = torch.optim.SGD(self.net.parameters(), lr=learning_rate)
        loss_fn = torch.nn.CrossEntropyLoss().to(self.ctx.device)
        info(f"Starting Training - Round {config['server-round']}")

        loss = train(
            self.net,
            self.trainloader,
            self.ctx.device,
            optim,
            loss_fn,
            epochs=local_epochs,
            input_key="img",
            target_key="label",
        )

        metrics = OrderedDict(
            client=self.ctx.simple_id,
            computing_start_time=tik,
            computing_finish_time=time.perf_counter(),
            loss=loss
        )
        debug(f"Training Metrics: {metrics}")
        info(f"Finished Training - Round {config['server-round']}")
        return get_weights(self.net), len(self.trainloader.dataset), metrics

    def evaluate(self, parameters, config):
        """Evaluate the model on the data this client has."""
        if not self.valloader:
            warning("No validation data found, returning 0.0 for loss")
            return 0.0, 0, {}

        set_weights(self.net, parameters)
        tik = time.perf_counter()
        info(f"Starting Evaluation - Round {config['server-round']}")
        loss, accuracy = test(
            self.net,
            self.valloader,
            self.ctx.device,
            input_key="img",
            target_key="label",
        )
        metrics = OrderedDict(
            client=self.ctx.simple_id,
            computing_start_time=tik,
            computing_finish_time=time.perf_counter(),
            loss=loss,
            accuracy=accuracy,
        )
        debug(f"Eval Metrics: {metrics}")
        info(f"Finished Evaluation - Round {config['server-round']}")
        return loss, len(self.valloader.dataset), metrics

    def get_properties(self, config: Config) -> dict[str, Scalar]:
        result = OrderedDict()
        props_type = config.get("props_type", '')
        metrics_agg = config.get("metrics_agg", "last")
        result["simple_id"] = self.ctx.simple_id
        if props_type == "system":
            result.update(client_metrics_utils.get_client_properties())
        elif props_type == "metrics" and self.metrics_collector:
            result.update(self.metrics_collector.get_metrics(aggregation=metrics_agg))
        elif props_type == "dataset":
            result.update(client_metrics_utils.get_dataset_info(self.trainloader, self.valloader))
        debug(f"Properties: {result}")
        return result


def init_client(context: Context):
    client_cfg: ClientConfig = setup_config(CONTAINER_CONFIG_PATH, "client", ClientConfig)
    dataset_cfg: DatasetConfig = setup_config(CONTAINER_CONFIG_PATH, "dataset", DatasetConfig)
    simple_id = context.node_config["cid"]
    log_file = Path(CONTAINER_LOG_PATH) / f"client_{context.node_config['cid']}.log"
    configure_logger("default", client_cfg.log_to_stream, log_file, client_cfg.logging_level)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    ctx = ClientContext(
        simple_id=simple_id,
        flwr_ctx=context,
        client_cfg=client_cfg,
        dataset_cfg=dataset_cfg,
        device=device
    )

    trainloader = get_dataloader(
        CONTAINER_DATA_PATH, dataset_cfg.name,
        simple_id, batch_size=client_cfg.train_batch_size,
        split="train", shuffle=True
    )

    valloader = get_dataloader(
        CONTAINER_DATA_PATH, dataset_cfg.name, simple_id,
        batch_size=client_cfg.val_batch_size, split="test"
    )

    if client_cfg.zmq["enable"]:
        init_zmq("default", client_cfg.zmq["host"], client_cfg.zmq["port"])
        system_props = client_metrics_utils.get_client_properties()
        to_zmq(f"client-props", {"client_id": ctx.simple_id, "system": system_props})

    metrics_collector = None
    if client_cfg.collect_metrics:
        metrics_collector = MetricsCollector(
            interval=client_cfg.collect_metrics_interval,
            server_address=client_cfg.server_address,
            publish_callback=lambda metrics: to_zmq(
                "client-props",
                {"client_id": ctx.simple_id, "metrics": metrics}
            ) if client_cfg.zmq["enable"] else None
        )

    model = Net()
    return FlowerClient(ctx, model, trainloader, valloader, metrics_collector)


def client_fn(context: Context):
    """Construct a Client that will be run in a ClientApp."""
    global flwr_client
    if not flwr_client:
        flwr_client = init_client(context)
    return flwr_client.to_client()


# Flower ClientApp
flwr_client = None
app = ClientApp(client_fn)
