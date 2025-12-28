from owrx.config.core import CoreConfig

import threading
import os.path
import os
import re

import logging

logger = logging.getLogger(__name__)


class CpuUsageThread(threading.Thread):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with CpuUsageThread.creationLock:
            if CpuUsageThread.sharedInstance is None:
                CpuUsageThread.sharedInstance = CpuUsageThread()
        return CpuUsageThread.sharedInstance

    def __init__(self):
        self.clients = []
        self.doRun = True
        self.last_worktime = 0
        self.last_idletime = 0

        # Determine where to read CPU temperature from
        tempFile = CoreConfig().get_temperature_sensor()
        if tempFile is not None and os.path.isfile(tempFile):
            self.tempFile = tempFile
        else:
            self.tempFile = None

        # Check sensors in /sys/class/thermal
        if self.tempFile is None:
            tempRoot = "/sys/class/thermal"
            try:
                for file in os.listdir(tempRoot):
                    if re.match(r"thermal_zone\d+", file):
                        tempFile = tempRoot + "/" + file + "/temp"
                        if os.path.isfile(tempFile):
                            self.tempFile = tempFile
                            break
            except Exception:
                pass

        # Check monitors in /sys/class/hwmon
        if self.tempFile is None:
            tempRoot = "/sys/class/hwmon"
            try:
                for file in os.listdir(tempRoot):
                    if re.match(r"hwmon\d+", file):
                        tempFile = tempRoot + "/" + file + "/device/temp"
                        if os.path.isfile(tempFile):
                            self.tempFile = tempFile
                            break
            except Exception:
                pass

        self.endEvent = threading.Event()
        self.startLock = threading.Lock()
        super().__init__()

    def run(self):
        logger.debug("cpu usage thread starting up")
        while self.doRun:
            try:
                cpu_usage = self.get_cpu_usage()
                temperature = self.get_temperature()
                (voltage, current, charge, charger) = self.get_battery()
            except:
                cpu_usage = 0
                temperature = 0
                voltage = 0.0
                current = 0.0
                charger = False
                charge = 0
            for c in self.clients:
                c.write_temperature(temperature)
                c.write_cpu_usage(cpu_usage)
                if voltage > 0.0:
                    c.write_battery({
                        "voltage": voltage,
                        "current": current,
                        "charger": charger,
                        "charge":  charge
                    })
            self.endEvent.wait(timeout=3)
        logger.debug("cpu usage thread shut down")

    def get_temperature(self):
        # Must have temperature file
        if self.tempFile is None:
            return 0
        # Try opening and reading file
        try:
            f = open(self.tempFile, "r")
        except:
            return 0
        line = f.readline()
        f.close()
        # Try parsing read temperature
        try:
            return int(line) // 1000
        except:
            return 0

    def get_cpu_usage(self):
        try:
            f = open("/proc/stat", "r")
        except:
            return 0  # Workaround, possibly we're on a Mac
        line = ""
        while not "cpu " in line:
            line = f.readline()
        f.close()
        spl = line.split(" ")
        worktime = int(spl[2]) + int(spl[3]) + int(spl[4])
        idletime = int(spl[5])
        dworktime = worktime - self.last_worktime
        didletime = idletime - self.last_idletime
        rate = float(dworktime) / (didletime + dworktime)
        self.last_worktime = worktime
        self.last_idletime = idletime
        if self.last_worktime == 0:
            return 0
        return rate

    def get_battery(self):
        voltage = 0.0
        current = 0.0
        charger = False
        charge  = 0.0
        try:
            f = open("/tmp/battery", "r")
            line = f.readline()
            f.close()
            m = re.match(r"(\d+\.\d+)V(\S?)\s+(\d+\.\d+)A\s+(\d+)%", line)
            if m:
                voltage = float(m.group(1))
                charger = m.group(2) == "!"
                current = float(m.group(3))
                charge  = int(m.group(4))
        except:
            pass
        return (voltage, current, charge, charger)

    def add_client(self, c):
        self.clients.append(c)
        with self.startLock:
            if not self.is_alive():
                self.start()

    def remove_client(self, c):
        try:
            self.clients.remove(c)
        except ValueError:
            pass
        if not self.clients:
            self.shutdown()

    def shutdown(self):
        with CpuUsageThread.creationLock:
            CpuUsageThread.sharedInstance = None
        self.doRun = False
        self.endEvent.set()
