# Abstract Traffic Pattern Classes
import shlex
from enum import Enum
from pathlib import Path
from typing import List, Any, Optional

from containernet_code.background_traffic.traffic_patterns import TrafficPattern


# Abstract Traffic Generator Classes
class TrafficGenerator:
    """Abstract base class for traffic generators."""

    def __init__(self, cfg, logger, log_path, **kwargs):
        self.cfg = cfg
        self.log_path = log_path
        self.logger = logger

    def start_flow(self, src: Any, dst: Any, rate: float, flow_id: str) -> bool:
        """Start a traffic flow between two hosts."""
        pass

    def stop_flows(self, hosts: List[Any]) -> None:
        """Stop all flows for given hosts."""
        pass


class IperfGenerator(TrafficGenerator):
    """Iperf3-based traffic generator."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.port = 12345
        self.pattern: Optional[TrafficPattern] = kwargs.get("pattern", None)

    def start_flow(self, src_host, dst_host, rate: float, flow_id: str) -> bool:
        """Start an iperf3 flow."""

        if not self.pattern:
            self.logger.error("Traffic pattern not defined for IperfGenerator")
            return False

        try:
            # Generate traffic patterns
            rates = self.pattern.generate_rates(rate)
            intervals = self.pattern.generate_intervals()

            # Prepare command arguments
            rates_str = shlex.quote(" ".join(map(str, rates)))
            intervals_str = shlex.quote(" ".join(map(str, intervals)))
            log_file = self.log_path / f"{flow_id}_iperf.txt"

            # Start server and client
            dst_host.cmd(f"./start_iperf.sh server {self.port} {log_file}")
            src_host.cmd(f"./start_iperf.sh client {dst_host.IP()} {self.port} "
                         f"{rates_str} {intervals_str} {self.pattern.parallel_streams} {log_file}")

            self.logger.debug(f"Iperf flow started: {flow_id} (port {self.port})")
            self.port += 1
            return True

        except Exception as e:
            self.logger.error(f"Failed to start iperf flow {flow_id}: {e}")
            return False

    def stop_flows(self, hosts: List[Any]) -> None:
        """Stop all iperf flows."""
        for host in hosts:
            host.cmd("pkill -f 'iperf3'")
        self.logger.info("All iperf flows stopped")


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

    def start_flow(self, src_host: Any, dst_host: Any, rate: float, flow_id: str) -> bool:
        """Start a tcpreplay flow."""
        try:
            # Find PCAP files for this flow
            pcap_files = self._find_pcap_files(flow_id)
            if not pcap_files:
                self.logger.warning(f"No PCAP files found for {flow_id}")
                return False

            # Calculate replay speed
            multiplier = self.replay_multiplier * (rate / 10.0)

            log_file = self.log_path / f"{flow_id}_tcpreplay.log"
            loop_flag = "--loop=0" if self.replay_loop else ""
            pcap_list = " ".join(pcap_files)

            src_host.cmd(f"./start_tcpreplay.sh {dst_host.IP()} {multiplier} "
                         f"'{pcap_list}' {loop_flag} {log_file} &")

            self.logger.info(f"TCPreplay flow started: {flow_id} (multiplier: {multiplier:.2f})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start tcpreplay flow {flow_id}: {e}")
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

    def stop_flows(self, hosts: List[Any]) -> None:
        """Stop all tcpreplay flows."""
        for host in hosts:
            host.cmd("pkill -f 'tcpreplay'")
        self.logger.info("All tcpreplay flows stopped")


class BGTrafficGenerators(Enum):
    IPERF = IperfGenerator
    TCP_REPLAY = TcpreplayGenerator

    @classmethod
    def create(cls, cfg, **kwargs):
        name = cfg.bg.generator_config["name"].upper()
        return cls[name].value(**kwargs)
