try:
    from .binaryview import ESPFirmware
    ESPFirmware.register()
except ImportError:
    pass
