from pyrav4l2 import Device

dev = Device("/dev/video0")
available_formats = dev.available_formats

for color_format in available_formats.keys():
    print(f"{color_format}:")
    for frame_size in available_formats[color_format]:
        print(f"    {frame_size}")
    print()

color_format = list(available_formats.keys())[0]
frame_size = available_formats[color_format][0]
dev.set_format(color_format, frame_size)