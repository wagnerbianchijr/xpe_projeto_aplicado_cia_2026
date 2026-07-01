"""Pure IIoT value model: per-sensor mean-reverting random walk with rare
anomalies and dropouts. No database or wall-clock access — all randomness is
injected so behavior is deterministic under a seeded RNG."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from catalog import SensorSpec

COUNTER_METRIC = "production_count"

_STEP_FRAC = 0.02       # random-walk step stddev as a fraction of the range
_REVERT_FRAC = 0.05     # pull toward baseline each tick
_SLACK_FRAC = 0.10      # how far past the limits a normal value may wander
_ANOMALY_FRAC = (0.05, 0.20)  # how far past a limit an anomaly is pushed


@dataclass
class Reading:
    time: datetime
    sensor_id: int
    value: float
    quality: int = 0


@dataclass
class SensorState:
    last_value: float
    dropout_until: datetime | None = None
    counter: float = 0.0


class Generator:
    def __init__(
        self,
        specs,
        rng,
        p_anomaly: float = 0.005,
        p_dropout: float = 0.002,
        dropout_min_s: float = 30.0,
        dropout_max_s: float = 120.0,
    ):
        self._specs = list(specs)
        self._rng = rng
        self._p_anomaly = p_anomaly
        self._p_dropout = p_dropout
        self._dropout_min_s = dropout_min_s
        self._dropout_max_s = dropout_max_s
        self._state: dict[int, SensorState] = {
            spec.sensor_id: SensorState(last_value=self._baseline(spec))
            for spec in self._specs
        }

    @staticmethod
    def _baseline(spec: SensorSpec) -> float:
        if spec.min_limit is not None and spec.max_limit is not None:
            return (spec.min_limit + spec.max_limit) / 2
        return 0.0

    def tick(self, now: datetime) -> list[Reading]:
        readings: list[Reading] = []
        for spec in self._specs:
            state = self._state[spec.sensor_id]

            # 1. Currently dropped out -> stay silent until the window ends.
            if state.dropout_until is not None:
                if now < state.dropout_until:
                    continue
                state.dropout_until = None

            # 2. Maybe start a new dropout.
            if self._rng.random() < self._p_dropout:
                secs = self._rng.uniform(self._dropout_min_s, self._dropout_max_s)
                state.dropout_until = now + timedelta(seconds=secs)
                continue

            # 3. Monotonic counter (production_count) or any sensor without a
            #    numeric range: ignore the random walk, emit a running counter.
            if spec.metric == COUNTER_METRIC or spec.min_limit is None or spec.max_limit is None:
                state.counter += self._rng.randint(1, 8)
                readings.append(Reading(now, spec.sensor_id, state.counter))
                continue

            # 4. Mean-reverting random walk, clamped to limits + slack.
            span = spec.max_limit - spec.min_limit
            baseline = self._baseline(spec)
            step = self._rng.gauss(0, span * _STEP_FRAC)
            pulled = state.last_value + step + (baseline - state.last_value) * _REVERT_FRAC
            slack = span * _SLACK_FRAC
            value = min(max(pulled, spec.min_limit - slack), spec.max_limit + slack)

            # 5. Rare anomaly pushes the value out of range (drives 'alerta').
            if self._rng.random() < self._p_anomaly:
                value = self._anomaly(spec, span)

            state.last_value = value
            readings.append(Reading(now, spec.sensor_id, value))
        return readings

    def _anomaly(self, spec: SensorSpec, span: float) -> float:
        lo, hi = _ANOMALY_FRAC
        overshoot = self._rng.uniform(lo, hi) * span
        if self._rng.random() < 0.5:
            return spec.min_limit - overshoot
        return spec.max_limit + overshoot
