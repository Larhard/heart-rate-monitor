#!/usr/bin/env python3

import argparse
import matplotlib.pyplot as plt
import matplotlib.animation as anim

from datetime import datetime

import gatt

plt.ion()

class DeviceManager(gatt.DeviceManager):
    pass

class Device(gatt.Device):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.heart_rate_measurement = None
        self.heart_rate_consumers = []

    def connect_succeeded(self):
        super().connect_succeeded()
        print(f"{self.mac_address}: Connected")

    def connect_failed(self, error):
        super().connect_failed(error)
        print(f"{self.mac_address}: Connection failed: {str(error)}")

    def get_characteristic(self, uuid):
        for service in self.services:
            for characteristic in service.characteristics:
                if characteristic.uuid == uuid:
                    return characteristic

        raise ValueError(f"Characteristic not found: {uuid}")

    def services_resolved(self):
        super().services_resolved()

        self.heart_rate_measurement = self.get_characteristic("00002a37-0000-1000-8000-00805f9b34fb")

        self.heart_rate_measurement.enable_notifications()

    def characteristic_value_updated(self, characteristic, value):
        if (characteristic.uuid == self.heart_rate_measurement.uuid):
            heart_rate_data = self.interpret_heart_rate(value)
            for consumer in self.heart_rate_consumers:
                consumer(heart_rate_data)

    def interpret_heart_rate(self, value):
        result = {}

        position = 0

        result["timestamp"] = datetime.utcnow()

        flags = value[position]
        position += 1

        result["heart_rate_value_format"] = "uint16" if flags & (1 << 0) else "uint8"
        result["sensor_contact_detected"] = bool(flags & (1 << 1))
        result["sensor_contact_supported"] = bool(flags & (1 << 2))
        result["energe_expended_present"] = bool(flags & (1 << 3))
        result["rr_intervals_present"] = bool(flags & (1 << 4))

        if result["heart_rate_value_format"] == "uint8":
            result["heart_rate_measurement"] = int.from_bytes(value[position:position+1], byteorder="little")
            position += 1
        elif result["heart_rate_value_format"] == "uint16":
            result["heart_rate_measurement"] = int.from_bytes(value[position:position+2], byteorder="little")
            position += 2
        else:
            assert False

        if result["energe_expended_present"]:
            result["energy_expended"] = int.from_bytes(value[position:position+2], byteorder="little")
            position += 2
        else:
            result["energy_expended"] = None

        if result["rr_intervals_present"]:
            result["rr_intervals"] = []  # in 1/1024 of second
            while position < len(value):
                result["rr_intervals"].append(int.from_bytes(value[position:position+2], byteorder="little"))
                position += 2
        else:
            result["rr_intervals"] = None

        return result

class Plotter:
    def __init__(self):
        self.xs = []
        self.ys = []

        self.fig = None
        self.ax = None
        self.animation = None

    def append_data(self, x, y):
        self.xs.append(x)
        self.ys.append(y)

    def update(self, i):
        self.ax.clear()
        self.ax.plot(self.xs, self.ys, "r-")

    def start(self):
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111)

        self.animation = anim.FuncAnimation(self.fig, self.update)

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mac", required=True)
    parser.add_argument("--adapter", default="hci0")
    args = parser.parse_args(argv)

    manager = DeviceManager(adapter_name=args.adapter)
    device = Device(mac_address=args.mac, manager=manager)
    plotter = Plotter()

    # device.heart_rate_consumers.append(lambda x: print(x))
    device.heart_rate_consumers.append(lambda x: plotter.append_data(x["timestamp"], x["heart_rate_measurement"]))

    plotter.start()
    device.connect()
    manager.run()

if __name__ == "__main__":
    main()
