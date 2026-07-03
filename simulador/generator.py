"""Modelo puro de valores IIoT: random walk com reversão à média por sensor, com
anomalias e dropouts raros. Sem acesso a banco ou relógio — toda aleatoriedade é
injetada, então o comportamento é determinístico sob um RNG com seed."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from catalog import SensorSpec

COUNTER_METRIC = "production_count"

_STEP_FRAC = 0.02       # desvio-padrão do passo do random walk como fração da faixa
_REVERT_FRAC = 0.05     # puxão em direção à baseline a cada tick
_SLACK_FRAC = 0.10      # quanto além dos limites um valor normal pode oscilar
_ANOMALY_FRAC = (0.05, 0.20)  # quanto além de um limite uma anomalia é empurrada


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

            # 1. Em dropout no momento -> fica em silêncio até a janela terminar.
            if state.dropout_until is not None:
                if now < state.dropout_until:
                    continue
                state.dropout_until = None

            # 2. Talvez iniciar um novo dropout.
            if self._rng.random() < self._p_dropout:
                secs = self._rng.uniform(self._dropout_min_s, self._dropout_max_s)
                state.dropout_until = now + timedelta(seconds=secs)
                continue

            # 3. Contador monotônico (production_count) ou qualquer sensor sem
            #    faixa numérica: ignora o random walk, emite um contador crescente.
            if spec.metric == COUNTER_METRIC or spec.min_limit is None or spec.max_limit is None:
                state.counter += self._rng.randint(1, 8)
                readings.append(Reading(now, spec.sensor_id, state.counter))
                continue

            # 4. Random walk com reversão à média, limitado aos limites + folga.
            span = spec.max_limit - spec.min_limit
            baseline = self._baseline(spec)
            step = self._rng.gauss(0, span * _STEP_FRAC)
            pulled = state.last_value + step + (baseline - state.last_value) * _REVERT_FRAC
            slack = span * _SLACK_FRAC
            value = min(max(pulled, spec.min_limit - slack), spec.max_limit + slack)

            # 5. Anomalia rara empurra o valor para fora da faixa (gera 'alerta').
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
