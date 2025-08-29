import logging
import platform
import socket
import sys
import time
from collections import deque
from typing import Dict, Any, List

import psutil
import torch
from apscheduler.schedulers.background import BackgroundScheduler


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

    def _collect_system_metrics(self):
        self.cpu_usage.append(psutil.cpu_percent())
        self.ram_usage.append(psutil.virtual_memory().percent)

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


def get_os_info() -> Dict[str, Any]:
    """Get basic system information."""
    return {
        "os_type": platform.system(),
        "os_release": platform.release(),
        "python_version": sys.version.split()[0],
    }


def get_hardware_info() -> Dict[str, Any]:
    """Get hardware information including CPU, RAM, and GPU details."""
    info = {
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "total_ram": psutil.virtual_memory().total / (1024 ** 2),  # MB
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
        "val_samples": len(valloader.dataset),
        "batch_size": trainloader.batch_size,
    }


def get_training_params(local_epochs: int, learning_rate: float) -> Dict[str, Any]:
    """Get training parameters."""
    return {
        "local_epochs": local_epochs,
        "learning_rate": learning_rate,
    }


def get_client_properties(os=True,
                          hardware=True,
                          network=True,
                          interface_name="flc") -> Dict[str, Dict[str, Any]]:
    """Get all client properties combined."""
    properties = {}
    if os:
        properties.update(get_os_info())
    if hardware:
        properties.update(get_hardware_info())
    if network:
        properties.update(get_network_info(interface_name))
    return properties
