# logging_manager.py
import atexit
import csv
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, Tuple

import zmq
from flwr.common.logger import FLOWER_LOGGER

_loggers: Dict[str, logging.Logger] = {}
_lock = Lock()

_csv_files: Dict[str, tuple] = {}

_zmq_publishers: Dict[str, zmq.Socket] = {}  # name -> socket
_zmq_ip_port_map: Dict[Tuple[str, int], str] = {}  # (ip, port) -> name
_zmq_context: Optional[zmq.Context] = None


def configure_logger(name: str, log_to_stream: bool = True, log_file: Optional[str | Path] = None,
                     level: str = "INFO") -> logging.Logger:
    """Configure a named logger."""
    with _lock:
        if name in _loggers:
            return _loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(level.upper())
        logger.propagate = False
        logger.handlers.clear()

        formatter = logging.Formatter(
            f"\033[95m[{name}] %(levelname)s %(asctime)s\t: %(message)s\033[0m",
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Console handler
        if log_to_stream:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        # File handler
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        _loggers[name] = logger
        return logger


def _log(level: str, message: str, logger_name: str = "default"):
    logger = _loggers.get(logger_name)
    if logger:
        getattr(logger, level)(message)


def info(message: str, logger_name: str = "default"):
    _log("info", message, logger_name)


def debug(message: str, logger_name: str = "default"):
    _log("debug", message, logger_name)


def warning(message: str, logger_name: str = "default"):
    _log("warning", message, logger_name)


def error(message: str, logger_name: str = "default"):
    _log("error", message, logger_name)


def to_csv(file_path: str, row_dict: dict = None, fieldnames=None):
    """Write row_dict to CSV, initializing fieldnames if needed."""
    with _lock:
        if file_path not in _csv_files:
            f = open(file_path, "a", newline="")
            fnames = list(row_dict.keys()) if row_dict else fieldnames or []
            FLOWER_LOGGER.info(f"Creating CSV file {file_path} with fieldnames {fnames}")
            writer = csv.DictWriter(f, fieldnames=fnames)
            if f.tell() == 0 and fnames:
                writer.writeheader()
            _csv_files[file_path] = (f, writer)
        f, writer = _csv_files[file_path]

        if row_dict:
            writer.writerow(row_dict)
            f.flush()


def init_zmq(name: str, ip: str = "*", port: int = 5555) -> zmq.Socket:
    """Initialize a ZMQ publisher, enforcing unique (ip, port)."""
    global _zmq_context
    key = (ip, port)

    with _lock:
        if name in _zmq_publishers:
            return _zmq_publishers[name]

        if key in _zmq_ip_port_map:
            existing_name = _zmq_ip_port_map[key]
            raise RuntimeError(f"ZMQ port {ip}:{port} already used by publisher '{existing_name}'")

        if _zmq_context is None:
            _zmq_context = zmq.Context()

        socket = _zmq_context.socket(zmq.PUB)
        socket.bind(f"tcp://{ip}:{port}")

        _zmq_publishers[name] = socket
        _zmq_ip_port_map[key] = name
        return socket


def to_zmq(topic: str, message: dict, ignore_error=True, name: str = "default"):
    """Publish a message via ZMQ using the publisher name."""
    with _lock:
        if name not in _zmq_publishers:
            if ignore_error:
                return
            else:
                raise RuntimeError(f"ZMQ publisher '{name}' is not initialized. Call init_zmq first.")
        socket = _zmq_publishers[name]
        socket.send_multipart([
            topic.encode("utf-8"),
            json.dumps(message).encode("utf-8")
        ])


def close_all():
    """Close all resources: CSV, ZMQ, loggers."""
    global _zmq_context
    with _lock:
        # Close CSV files
        for file_handle, _ in _csv_files.values():
            file_handle.close()
        _csv_files.clear()

        # Close ZMQ
        for socket in _zmq_publishers.values():
            socket.close()
        _zmq_publishers.clear()
        _zmq_ip_port_map.clear()

        if _zmq_context is not None:
            _zmq_context.term()
            _zmq_context = None

        # Close all logger handlers
        for logger in _loggers.values():
            for handler in logger.handlers:
                handler.close()
            logger.handlers.clear()
        _loggers.clear()


# Register cleanup on exit
atexit.register(close_all)
