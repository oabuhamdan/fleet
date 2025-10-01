# Abstract Traffic Pattern Classes
import time
from datetime import datetime, timedelta
from itertools import cycle
from pathlib import Path
from typing import List, Any, Type

from apscheduler.schedulers.background import BackgroundScheduler
from mininet.node import Host

from common.loggers import error, info, configure_logger

LOGGER_NAME = "tg"


# Abstract Traffic Generator Classes
class TrafficGenerator:
    """Abstract base class for traffic generators."""

    def __init__(self, cfg, log_path, **kwargs):
        self.cfg = cfg
        self.log_path = log_path
        configure_logger(LOGGER_NAME, log_to_stream=False, log_file=f"{log_path}/traffic_generator.log", level="INFO")
        self.streams = {}

    def init_stream(self, src: Any, dst: Any, rate: float, stream_id: str) -> bool:
        """Start a traffic flow between two hosts."""
        pass

    def start_streams(self) -> None:
        """Start all flows for given hosts."""
        pass

    def stop_streams(self) -> None:
        """Stop all flows for given hosts."""
        pass


class BGStreamInfo:
    """Represents a single iperf flow."""

    def __init__(self, stream_id, src: Host, dst: Host, port: int, parallel: int, rate_list, interval_list):
        self.stream_id = stream_id
        self.src = src
        self.dst = dst
        self.port = port
        self.rate_list = rate_list
        self.interval_list = interval_list
        self.parallel = parallel


class IperfGenerator(TrafficGenerator):
    """Iperf3-based traffic generator."""

    def __init__(self, cfg, log_path, **kwargs):
        super().__init__(cfg, log_path)
        self.rate_dist, self.intervals_dist = kwargs["pattern"]
        self.log_path = log_path
        self.port = cfg.get("base_port", 5000)
        self.p_streams = cfg.get("parallel_streams", 1)
        self.streams: dict[str, BGStreamInfo] = {}
        self.scheduler = BackgroundScheduler()

    def init_stream(self, src: Host, dst: Host, rate: float, stream_id: str):
        """Start a background traffic flow with dynamic rate changes."""
        port = self.port
        rates = self.rate_dist.generate(rate) // self.p_streams
        intervals = self.intervals_dist.generate(max(rate // 10, 5))  # scale time with rate
        self._write_rates_file(src, stream_id, rates, intervals)
        stream_info = BGStreamInfo(stream_id, src, dst, port, self.p_streams, rates, intervals)
        self.streams[stream_id] = stream_info
        self.port += 1

    @staticmethod
    def _write_rates_file(src, stream_id, rates, intervals) -> None:
        rates_file = f"/tmp/rates_{stream_id}.txt"
        rates_str = ",".join(map(str, rates))
        intervals_str = ",".join(map(str, intervals))
        src.cmd(f'echo "{rates_str}" > {rates_file}')
        src.cmd(f'echo "{intervals_str}" >> {rates_file}')

    def start_streams(self) -> None:
        for stream_info in self.streams.values():
            sid = stream_info.stream_id
            src, dst = stream_info.src, stream_info.dst
            port = stream_info.port
            parallel = stream_info.parallel
            dst.cmd("./scripts/iperf_runner.py server", sid, port, "&") # Start server
            time.sleep(1)
            src.cmd("./scripts/iperf_runner.py client", sid, dst.IP(), port, parallel, "&") # Start client
            info(f"Iperf flow started: {stream_info.stream_id} from {src.name} to {dst.name} on port {port}")

    def stop_streams(self) -> None:
        for stream_info in self.streams.values():
            print(f"Stopping iperf flow: {stream_info.stream_id}")
            sid = stream_info.stream_id
            for host in [stream_info.src, stream_info.dst]:
                host.pexec(["./scripts/iperf_runner.py", "stop", sid])
        print("All iperf flows stopped")

class TcpreplayGenerator(TrafficGenerator):
    """TCPreplay-based traffic generator."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pcap_dir = self.cfg.get("pcap_dir", None)
        self.replay_multiplier = self.cfg.get("replay_multiplier", 1.0)
        self.replay_loop = self.cfg.get("replay_loop", False)
        self.log_path = Path(self.log_path) / "tcpreplay_logs"
        if not self.pcap_dir:
            raise ValueError("PCAP directory must be specified for TCPreplay")

    def init_stream(self, src_host: Any, dst_host: Any, rate: float, stream_id: str) -> bool:
        """Start a tcpreplay flow."""
        try:
            # Find PCAP files for this flow
            pcap_files = self._find_pcap_files(stream_id)
            if not pcap_files:
                error(f"No PCAP files found for {stream_id}")
                return False

            # Calculate replay speed
            multiplier = self.replay_multiplier * (rate / 10.0)

            log_file = self.log_path / f"{stream_id}_tcpreplay.log"
            loop_flag = "--loop=0" if self.replay_loop else ""
            pcap_list = " ".join(pcap_files)

            src_host.pexec(["./start_tcpreplay.sh", dst_host.IP(), str(multiplier),
                            pcap_list, loop_flag, str(log_file)])

            info(f"TCPreplay flow started: {stream_id} (multiplier: {multiplier:.2f})")
            return True

        except Exception as e:
            error(f"Failed to start tcpreplay flow {stream_id}: {e}")
            return False

    def _find_pcap_files(self, flow_id: str) -> List[str]:
        """Find relevant PCAP files for a flow."""
        pcap_dir = Path(self.pcap_dir)
        if not pcap_dir.exists():
            return []

        # Look for PCAP files matching the flow pattern
        patterns = [
            f"{flow_id}*.pcap",
            f"*{flow_id}*.pcap",
            "*.pcap"  # Fallback
        ]

        for pattern in patterns:
            files = list(pcap_dir.glob(pattern))
            if files:
                return [str(f) for f in files[:3]]  # Limit to 3 files

        return []

    def stop_streams(self) -> None:
        """Stop all tcpreplay flows."""
        for host in self.streams:
            host.pexec(["pkill", "-f", "tcpreplay"])
        info("All tcpreplay flows stopped")


TRAFFIC_GENERATORS = {
    "iperf": IperfGenerator,
    "tcpreplay": TcpreplayGenerator
}


def get_traffic_generator(cfg, log_path, **kwargs) -> TrafficGenerator:
    generator_name = cfg.get("name", "iperf")
    generator_cls: Type[TrafficGenerator] = TRAFFIC_GENERATORS.get(generator_name, None)
    assert generator_cls, f"Unsupported traffic generator type: {generator_name}"
    return generator_cls(cfg, log_path, **kwargs)
