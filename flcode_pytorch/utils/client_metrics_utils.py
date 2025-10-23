import logging
import socket
import time
from collections import deque
from typing import Dict, Any, List

import psutil
import torch
from apscheduler.schedulers.background import BackgroundScheduler


def _read(path):
    with open(path) as f:
        return f.read().strip()


class MetricsCollector:
    def __init__(self,
                 collect_cpu_ram: bool = True,
                 collect_gpu: bool = True,
                 collect_latency: bool = True,
                 server_address: str = None,
                 window_size: int = 10,
                 interval: int = 5,
                 publish_callback=None
                 ):
        self.window_size = window_size
        self.interval = interval
        self.server_address = server_address
        self.collect_cpu_ram = collect_cpu_ram
        self.collect_gpu = collect_gpu
        self.collect_latency = collect_latency
        self.publish_callback = publish_callback

        self.cpu_usage = deque(maxlen=window_size)
        self.ram_usage = deque(maxlen=window_size)
        self.gpu_usage = deque(maxlen=window_size)
        self.gpu_memory = deque(maxlen=window_size)
        self.server_latency = deque(maxlen=window_size)

        self.scheduler = BackgroundScheduler()
        self.start()

    def start(self):
        self.scheduler.add_job(self._collect_metrics, 'interval', seconds=self.interval)
        self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def _collect_metrics(self):
        if self.collect_cpu_ram:
            self._collect_system_metrics()
        if self.collect_gpu and torch.cuda.is_available():
            self._collect_gpu_metrics()
        if self.collect_latency and self.server_address:
            self._collect_latency_metrics()
        if self.publish_callback:
            self.publish_callback(self.get_metrics(aggregation="last"))

    # Memory usage %
    def mem_percent(self):
        used = int(_read("/sys/fs/cgroup/memory.current"))
        limit = _read("/sys/fs/cgroup/memory.max")
        if limit == "max": return 0
        return round(100 * used / int(limit), 2)

    # CPU usage % over 1 second
    def cpu_percent(self):
        def usage():
            for line in _read("/sys/fs/cgroup/cpu.stat").splitlines():
                if line.startswith("usage_usec"):
                    return int(line.split()[1])
            return 0

        start = usage()
        time.sleep(self.interval)
        end = usage()
        return round((end - start) / (self.interval * 1_000_000) * 100, 2)

    def _collect_system_metrics(self):
        self.cpu_usage.append(self.cpu_percent())
        self.ram_usage.append(self.mem_percent())

    def _collect_gpu_metrics(self):
        try:
            self.gpu_usage.append(torch.cuda.utilization())
            gpu_memory = torch.cuda.memory_allocated() / torch.cuda.max_memory_allocated()
            self.gpu_memory.append(gpu_memory * 100)
        except Exception as e:
            logging.error("Failed to collect GPU metrics due to: %s", e)

    def _collect_latency_metrics(self):
        try:
            start_time = time.perf_counter()
            socket.create_connection((self.server_address, 80), timeout=1)
            latency = (time.perf_counter() - start_time) * 1000
            self.server_latency.append(latency)
        except Exception as e:
            logging.error("Failed to collect latency metrics due to: %s", e)

    def get_metrics(self, aggregation="last", get_cpu_ram=True, get_gpu=True, get_latency=True) -> Dict[
        str, List[float | int]]:
        def last(deque_list: deque) -> float | int:
            return deque_list[-1] if deque_list else 0.0

        def avg(deque_list: deque) -> float:
            return sum(deque_list) / len(deque_list) if deque_list else 0.0

        metrics = {}
        agg = last if aggregation == "last" else avg
        if self.collect_cpu_ram and get_cpu_ram:
            metrics["cpu_usage"] = agg(self.cpu_usage)
            metrics["ram_usage"] = agg(self.ram_usage)
        if self.collect_gpu and torch.cuda.is_available() and get_gpu:
            metrics["gpu_usage"] = agg(self.gpu_usage)
            metrics["gpu_memory"] = agg(self.gpu_memory)
        if self.collect_latency and self.server_address and get_latency:
            metrics["server_latency"] = agg(self.server_latency)
        return metrics


def get_cpu_limit():
    quota, period = _read("/sys/fs/cgroup/cpu.max").split()
    return None if quota == "max" else round(int(quota) / int(period), 2)


def get_total_ram_mb():
    val = _read("/sys/fs/cgroup/memory.max")
    return int(val) / (1024 ** 2) if val != "max" else 0


def get_hardware_info() -> Dict[str, Any]:
    info = {
        "cpu_limit": get_cpu_limit(),
        "total_ram": get_total_ram_mb()
    }

    if torch.cuda.is_available():
        info.update({
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_memory_total": torch.cuda.get_device_properties(0).total_memory / (1024 ** 3),  # GB
        })

    return info


def get_network_info(interface_prefix: str = "flc") -> Dict[str, Any]:
    """Get network interface information for interfaces starting with specified prefix."""
    network_info = {}

    for interface, addrs in psutil.net_if_addrs().items():
        if interface.startswith(interface_prefix):
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    network_info[f"{interface}_ipv4"] = addr.address
                elif addr.family == socket.AF_PACKET:
                    network_info[f"{interface}_mac"] = addr.address

    return network_info


def get_dataset_info(trainloader: Any, valloader: Any) -> Dict[str, Any]:
    """Get information about the dataset and data loaders."""
    return {
        "train_samples": len(trainloader.dataset),
        "val_samples": len(valloader.dataset) if valloader else 0,
        "batch_size": trainloader.batch_size,
    }


def get_training_params(local_epochs: int, learning_rate: float) -> Dict[str, Any]:
    """Get training parameters."""
    return {
        "local_epochs": local_epochs,
        "learning_rate": learning_rate,
    }


def get_client_properties(hardware=True,
                          network=True,
                          interface_name="flc") -> Dict[str, Any]:
    """Get all client properties combined."""
    properties = {}
    if hardware:
        properties.update(get_hardware_info())
    if network:
        properties.update(get_network_info(interface_name))
    return properties
