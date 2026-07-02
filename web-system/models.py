"""Linhas tipadas retornadas pela camada de consultas."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class LineRecordCount:
    line_id: int
    line_name: str
    count: int


@dataclass
class FailingSensor:
    sensor_id: int
    line_id: int
    line_name: str
    metric: str


@dataclass
class KpiSummary:
    ok: int
    alerta: int
    sem_dados: int
    failed: int
    lines: int
    production_today: float
    total_records: int
    records_by_line: list[LineRecordCount]


@dataclass
class SensorStatusRow:
    sensor_id: int
    line_id: int
    line_name: str
    metric: str
    unit: str
    value: float | None
    last_time: datetime | None
    status: str


@dataclass
class LivenessRow:
    sensor_id: int
    line_id: int
    metric: str
    last_time: datetime | None
    seconds_since_last: float | None
    is_failed: bool


@dataclass
class TimeseriesPoint:
    time: datetime
    value: float | None


@dataclass
class ViolationRow:
    bucket: datetime
    sensor_id: int
    line_id: int
    metric: str


@dataclass
class SensorMeta:
    sensor_id: int
    line_id: int
    metric: str
    unit: str
    min_limit: float | None
    max_limit: float | None
    description: str | None
