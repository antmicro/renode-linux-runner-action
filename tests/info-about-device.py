from pyrav4l2 import Device

dev = Device("/dev/video0")
print(f"Device name: {dev.device_name}")
print(f"Driver name: {dev.driver_name}")
if dev.is_video_capture_capable:
    print(f"Device supports video capturing")
else:
    print(f"Device does not support video capturing")