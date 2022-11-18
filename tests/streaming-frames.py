from pyrav4l2 import Device, Stream

dev = Device("/dev/video0")
for (i, frame) in enumerate(Stream(dev)):
    print(f"Frame {i}: {len(frame)} bytes")

    if i >= 9:
        break