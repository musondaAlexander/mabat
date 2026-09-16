"""Sensors section: temperatures, fans and power draw."""

from mabat.sections.sensors.collector import sensors
from mabat.sections.sensors.models import Fan, Power, SensorsReport, Temperature

__all__ = ["Fan", "Power", "SensorsReport", "Temperature", "sensors"]
