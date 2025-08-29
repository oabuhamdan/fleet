from enum import Enum
from typing import List

import numpy as np


class TrafficPattern:
    """Abstract base class for traffic patterns."""

    def __init__(self, **kwargs):
        self.base_interval = kwargs.pop("base_interval", 10.0)
        self.data_points = kwargs.pop("points", 100)
        self.min_rate = kwargs.pop("min_rate", 0.0)
        self.max_rate = kwargs.pop("max_rate", 100.0)
        self.parallel_streams = kwargs.pop("parallel_streams", 1)
        self.extras = kwargs

    def generate_rates(self, rate) -> List[float]:
        """Generate traffic rates for this pattern."""

    def generate_intervals(self) -> List[int]:
        """Generate time intervals for this pattern."""


class PoissonPattern(TrafficPattern):
    """Poisson-distributed traffic pattern."""

    def generate_rates(self, rate) -> List[float]:
        rates = np.random.poisson(rate, self.data_points)
        rates = np.clip(rates, self.min_rate, self.max_rate)
        return (rates / self.parallel_streams).tolist()

    def generate_intervals(self) -> List[int]:
        """Poisson-distributed intervals - bursty arrival times."""
        return np.random.poisson(self.base_interval, self.data_points).tolist()


class UniformPattern(TrafficPattern):
    """Uniformly distributed traffic pattern."""

    def generate_rates(self, rate) -> List[float]:
        rates = np.random.uniform(self.min_rate, min(rate, self.max_rate), self.data_points)
        return (rates / self.parallel_streams).tolist()

    def generate_intervals(self) -> List[int]:
        """Uniform intervals - steady, predictable timing."""
        intervals = np.random.uniform(self.base_interval * 0.5, self.base_interval * 1.5, self.data_points)
        return intervals.astype(int).tolist()


class NormalPattern(TrafficPattern):
    """Normally distributed traffic pattern."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.std_ratio = kwargs.get("std_ratio", 0.2)

    def generate_rates(self, rate) -> List[float]:
        std = rate * self.std_ratio
        rates = np.random.normal(rate, std, self.data_points)
        rates = np.clip(rates, self.min_rate, self.max_rate)
        return (rates / self.parallel_streams).tolist()

    def generate_intervals(self) -> List[int]:
        """Normal intervals - clustered around mean with some variation."""
        std = self.base_interval * self.std_ratio
        intervals = np.random.normal(self.base_interval, std, self.data_points)
        intervals = np.clip(intervals, 1, self.base_interval * 3)  # Reasonable bounds
        return intervals.astype(int).tolist()


class ExponentialPattern(TrafficPattern):
    """Exponentially distributed traffic pattern."""

    def generate_rates(self, rate) -> List[float]:
        rates = np.random.exponential(rate, self.data_points)
        rates = np.clip(rates, self.min_rate, self.max_rate)
        return (rates / self.parallel_streams).tolist()

    def generate_intervals(self) -> List[int]:
        """Exponential intervals - many short intervals, few long ones."""
        intervals = np.random.exponential(self.base_interval, self.data_points)
        intervals = np.clip(intervals, 1, self.base_interval * 5)  # Cap very long intervals
        return intervals.astype(int).tolist()


class BurstyPattern(TrafficPattern):
    """Bursty traffic pattern with high rate bursts and low background."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.burst_ratio = kwargs.get("burst_ratio", 3.0)
        self.burst_probability = kwargs.get("burst_probability", 0.2)

    def generate_rates(self, rate) -> List[float]:
        rates = []
        for _ in range(self.data_points):
            if np.random.random() < self.burst_probability:
                rate = min(rate * self.burst_ratio, self.max_rate)
            else:
                rate = rate * 0.3  # Low background rate
            rates.append(max(rate, self.min_rate))
        return (np.array(rates) / self.parallel_streams).tolist()

    def generate_intervals(self) -> List[int]:
        """Bursty intervals - short intervals during bursts, long during quiet periods."""
        intervals = []
        for _ in range(self.data_points):
            if np.random.random() < self.burst_probability:
                # Short intervals during bursts
                interval = max(1, int(self.base_interval * 0.2))
            else:
                # Longer intervals during quiet periods
                interval = int(self.base_interval * np.random.uniform(1.0, 3.0))
            intervals.append(interval)
        return intervals


class SineWavePattern(TrafficPattern):
    """Sine wave pattern for periodic traffic."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.amplitude_ratio = kwargs.get("amplitude_ratio", 0.5)
        self.cycles = kwargs.get("cycles", 2.0)

    def generate_rates(self, rate) -> List[float]:
        t = np.linspace(0, self.cycles * 2 * np.pi, self.data_points)
        amplitude = rate * self.amplitude_ratio
        rates = rate + amplitude * np.sin(t)
        rates = np.clip(rates, self.min_rate, self.max_rate)
        return (rates / self.parallel_streams).tolist()

    def generate_intervals(self) -> List[int]:
        """Sine wave intervals - periodic variation in timing."""
        t = np.linspace(0, self.cycles * 2 * np.pi, self.data_points)
        amplitude = self.base_interval * 0.3  # 30% variation
        intervals = self.base_interval + amplitude * np.sin(t + np.pi)  # Phase shift for inverse relationship
        intervals = np.clip(intervals, 1, self.base_interval * 2)
        return intervals.astype(int).tolist()


class StepPattern(TrafficPattern):
    """Step function pattern with discrete rate levels."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.steps = kwargs.get("steps", 5)

    def generate_rates(self, rate) -> List[float]:
        step_size = self.data_points // self.steps
        rates = []
        for step in range(self.steps):
            step_rate = rate * (0.2 + 0.8 * step / (self.steps - 1))
            step_rate = min(step_rate, self.max_rate)
            rates.extend([step_rate] * step_size)

        # Fill remaining
        while len(rates) < self.data_points:
            rates.append(rates[-1])

        return (np.array(rates) / self.parallel_streams).tolist()

    def generate_intervals(self) -> List[int]:
        """Step intervals - discrete interval levels that change with rate steps."""
        step_size = self.data_points // self.steps
        intervals = []
        for step in range(self.steps):
            # Inverse relationship: higher rates get shorter intervals
            step_interval = int(self.base_interval * (1.5 - 0.8 * step / (self.steps - 1)))
            step_interval = max(1, step_interval)  # Minimum 1 second
            intervals.extend([step_interval] * step_size)

        # Fill remaining
        while len(intervals) < self.data_points:
            intervals.append(intervals[-1])

        return intervals


class BGTrafficPatterns(Enum):
    POISSON = PoissonPattern
    UNIFORM = UniformPattern
    NORMAL = NormalPattern
    EXPONENTIAL = ExponentialPattern
    BURSTY = BurstyPattern
    SINE = SineWavePattern
    STEP = StepPattern

    @classmethod
    def create(cls, cfg, **kwargs):
        name = cfg.bg.pattern_config["name"].upper()
        return cls[name].value(**kwargs)
