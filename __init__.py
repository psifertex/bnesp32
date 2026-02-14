try:
    from .binaryview import ESP32C3Firmware
    ESP32C3Firmware.register()
except ImportError:
    pass
