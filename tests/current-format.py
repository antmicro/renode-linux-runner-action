from pyrav4l2 import Device

dev = Device("/dev/video0")
color_format, frame_size = dev.get_format()
print(f"Color format: {color_format}")
print(f"Frame size: {frame_size}")