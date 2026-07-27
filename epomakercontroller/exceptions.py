"""Typed exceptions for the Epomaker controller package."""


class EpomakerError(Exception):
    """Base exception for all Epomaker controller errors."""


class DeviceNotOpenError(EpomakerError):
    """Raised when an operation requires an open HID device but none is available."""


class DeviceCommunicationError(EpomakerError):
    """Raised when the HID device cannot be contacted or rejects a transfer."""


class ProtocolError(EpomakerError):
    """Raised when a report or command violates the expected HID protocol shape."""


class CommandNotPreparedError(ProtocolError):
    """Raised when a multi-packet command is sent before its payload is ready."""


class ConfigError(EpomakerError):
    """Raised when configuration data is missing, invalid, or unsupported."""


class UnsupportedImageError(EpomakerError):
    """Raised when an image/GIF cannot be loaded or is not a supported format."""
