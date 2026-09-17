"""Exceptions raised by the uitap local-device client."""


class UitapError(Exception):
    """Base class for all library errors."""


class DeviceConnectionError(UitapError):
    """The device service could not be reached."""


class DeviceResponseError(UitapError):
    """The device returned an HTTP error or malformed response."""

    def __init__(self, message, *, status=None, body=""):
        super().__init__(message)
        self.status = status
        self.body = body


class DeviceOperationError(UitapError):
    """The device accepted a request but reported an operation failure."""


class DeviceLockTimeoutError(UitapError):
    """Acquiring the local cross-process device lock timed out."""

    def __init__(self, lock_id: object, timeout: float | None = None):
        self.lock_id = str(lock_id)
        self.timeout = timeout
        detail = "without a timeout" if timeout is None else f"after {timeout:g}s"
        super().__init__(f"timed out acquiring device lock {detail}: {self.lock_id}")


class ProtocolError(UitapError):
    """An invalid WebSocket or device response was received."""


class TunnelError(UitapError):
    """A local USB port-forwarding tunnel could not be started or kept alive."""


class IProxyNotFoundError(TunnelError):
    """The configured iproxy executable is not installed or not executable."""
