from pyrav4l2 import Device

dev = Device("/dev/video0")
available_controls = dev.controls

for control in available_controls:
    print(control.name)
    dev.reset_control_to_default(control)