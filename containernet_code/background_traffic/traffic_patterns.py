from enum import Enum
from typing import List, Union, Tuple
import numpy as np


class BaseDistribution:
    def __init__(self, cfg, **kwargs):
        self.points = cfg.get("points", 100)
        self.min_val = cfg.get("min_val", None)
        self.max_val = cfg.get("max_val", None)
        self.kwargs = kwargs

    def generate(self, mean: float) -> np.ndarray:
        raise NotImplementedError

    def clip(self, values) -> np.ndarray:
        values = np.clip(values, self.min_val, self.max_val)
        return values


class PoissonDist(BaseDistribution):
    def generate(self, mean: float) -> np.ndarray:
        values = np.random.poisson(mean, self.points)
        return self.clip(values)


class UniformDist(BaseDistribution):
    def generate(self, mean: float) -> np.ndarray:
        low = self.kwargs.get("low", mean * 0.5)
        high = self.kwargs.get("high", mean * 1.5)
        values = np.random.uniform(low, high, self.points)
        return self.clip(values)


class NormalDist(BaseDistribution):
    def generate(self, mean: float) -> np.ndarray:
        std_ratio = self.kwargs.get("std_ratio", 0.2)
        std = mean * std_ratio
        values = np.random.normal(mean, std, self.points)
        return self.clip(values)


class ExponentialDist(BaseDistribution):
    def generate(self, mean: float) -> np.ndarray:
        values = np.random.exponential(mean, self.points)
        return self.clip(values)


class SineWaveDist(BaseDistribution):
    def generate(self, mean: float) -> np.ndarray:
        cycles = self.kwargs.get("cycles", 2.0)
        amplitude = self.kwargs.get("amplitude_ratio", 0.5) * mean
        t = np.linspace(0, cycles * 2 * np.pi, self.points)
        values = mean + amplitude * np.sin(t)
        return self.clip(values)


class StepDist(BaseDistribution):
    def generate(self, mean: float) -> np.ndarray:
        steps = self.kwargs.get("steps", 5)
        step_size = self.points // steps
        values = []
        for s in range(steps):
            level = mean * (0.2 + 0.8 * s / (steps - 1))
            values.extend([level] * step_size)
        while len(values) < self.points:
            values.append(values[-1])
        values = np.array(values)
        return self.clip(values)


DISTRIBUTIONS = {
    "poisson": PoissonDist,
    "uniform": UniformDist,
    "normal": NormalDist,
    "exponential": ExponentialDist,
    "sine": SineWaveDist,
    "step": StepDist,
}


def get_traffic_pattern(rate_dist: dict, time_dist: dict, **kwargs):
    rate_dist = DISTRIBUTIONS[rate_dist.get("name")](rate_dist, **kwargs)
    time_dist = DISTRIBUTIONS[time_dist.get("name")](time_dist, **kwargs)
    return rate_dist, time_dist
