"""Type stubs for Kodi's embedded xbmcgui module."""

NOTIFICATION_ERROR: int
NOTIFICATION_INFO: int
NOTIFICATION_WARNING: int

class DialogProgress:
    def create(self, heading: str, line1: str = ..., line2: str = ..., line3: str = ...) -> None: ...
    def update(self, percent: int, line1: str = ..., line2: str = ..., line3: str = ...) -> None: ...
    def iscanceled(self) -> bool: ...
    def close(self) -> None: ...

class Dialog:
    def yesno(
        self,
        heading: str,
        message: str,
        nolabel: str | None = ...,
        yeslabel: str | None = ...,
        autoclose: int = ...,
    ) -> bool: ...
    def yesnocustom(
        self,
        heading: str,
        message: str,
        customlabel: str,
        nolabel: str | None = ...,
        yeslabel: str | None = ...,
        autoclose: int = ...,
    ) -> int: ...
    def ok(self, heading: str, message: str) -> None: ...
    def notification(
        self,
        heading: str,
        message: str,
        icon: str | int = ...,
        time: int = ...,
    ) -> None: ...

class Window:
    def __init__(self, existingWindowId: int = ...) -> None: ...
    def getProperty(self, key: str) -> str: ...
    def setProperty(self, key: str, value: str) -> None: ...
    def clearProperty(self, key: str) -> None: ...
