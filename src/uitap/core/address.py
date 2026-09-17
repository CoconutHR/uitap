"""Device address parsing."""
from __future__ import annotations

from dataclasses import dataclass

from ..i18n import t


@dataclass(frozen=True)
class DeviceAddress:
    host: str
    port: int = 9096

    @classmethod
    def parse(cls, value: str | "DeviceAddress") -> "DeviceAddress":
        if isinstance(value, cls):
            return value
        value = value.strip().removeprefix("http://").removeprefix("https://").rstrip("/")
        if not value:
            raise ValueError(t("device_address_empty"))
        host, sep, port = value.rpartition(":")
        if not sep:
            return cls(value)
        if not host or not port.isdecimal() or not 1 <= int(port) <= 65535:
            raise ValueError(t("device_address_invalid"))
        return cls(host, int(port))

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"
