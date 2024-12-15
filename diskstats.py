#!/usr/bin/python3

import subprocess
import logging
from typing import Dict, List
import pprint
import datetime
import re
import socket
from enum import Enum
import os

DEBUG_LEVEL = os.environ.get("JMUTILS_DEBUG", "DEBUG")
logging.basicConfig(
    level=DEBUG_LEVEL,  # Set the lowest level you want to see (DEBUG logs everything)
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Log format
    handlers=[logging.StreamHandler()],  # Output logs to the terminal (stdout)
)

logger = logging.getLogger(__name__)


class DiskState(Enum):
    RUNNING = "running"
    IDLE = "idle"
    ACTIVE = "active"
    SLEEPING = "sleeping"
    STANDBY = "standby"
    LIVE = "live"
    UNKNOWN = "unknown"


RUNNING_STATES = [DiskState.RUNNING, DiskState.ACTIVE, DiskState.LIVE]


def get_disk_state(device_name: str) -> DiskState:
    try:
        # Run lsblk command to get the state of the disk
        result = subprocess.run(
            ["lsblk", "-o", "NAME,STATE", device_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Check if the command was successful
        if result.returncode != 0:
            raise IOError(f"Error running lsblk: {result.stderr}")
        # Parse the output
        lines = result.stdout.strip().split("\n")
        # NAME   STATE
        # sda    running
        # ├─sda1
        # └─sda2
        for line in lines[1:]:  # Skip header
            parts = line.split()
            if len(parts) == 2:
                return DiskState(parts[1])
    except Exception as e:
        raise IOError(f"An error occurred: {str(e)}")
    return DiskState.UNKNOWN


def parse_smartctl_output(value: str):
    # maybe already numeric
    try:
        return int(value)
    except ValueError:
        pass
    
    # 173 MaxAvgErase_Ct          0x0000   100   100   000    Old_age   Offline      -       13 (Average 2)
    # 194 Temperature_Celsius     0x0022   033   038   000    Old_age   Always       -       33 (Min/Max 19/38)
    if " (Average" in value:
        pos = value.find(" (Average")
        return parse_smartctl_output(value[0:pos])
    if " (Min/Max" in value:
        pos = value.find(" (Min/Max")
        return parse_smartctl_output(value[0:pos])

    # 170 Bad_Blk_Ct_Erl/Lat      0x0000   100   100   010    Old_age   Offline      -       0/8
    if re.match(r"^[0-9]+/[0-9]+$", value):
        values = value.split("/")
        return tuple([int(val) for val in values])
    
    # Available Spare Threshold:          10%
    if value.endswith("%"):
        return parse_smartctl_output(value[:-1])

    # Host Write Commands:                61,020,911
    if re.match("^[0-9,]*$", value):
        return int(value.replace(",", ""))

    # Data Units Read:                    2,321,992 [1.18 TB]
    match = re.match(r"^[0-9,]* \[([0-9.]+) (TB|GB|MB)\]$", value)
    if match:
        size, unit = match.groups()
        size = float(size)
        if unit == "TB":
            return int(size * 1024**4)
        elif unit == "GB":
            return int(size * 1024**3)
        elif unit == "MB":
            return int(size * 1024**2)

    # Temperature:                        55 Celsius
    if " Celsius" in value:
        return int(value.split()[0])

    # Critical Warning:                   0x00
    if value.startswith("0x"):
        return int(value, 16)

    return value


def get_smart_attributes(device_name: str) -> Dict[str, int]:
    logger.info(f"Getting disk attributes for {device_name}")
    try:
        # Run smartctl command to get SMART data
        args = ["sudo", "smartctl", "-A", "--device=auto", device_name]
        logger.debug(f"Running command: {' '.join(args)}")
        result = subprocess.run(
            ["sudo", "smartctl", "-A", "--device=auto", device_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Check if the command was successful
        if result.returncode != 0:
            msg = f"Error running smartctl: {result.stderr}"
            logger.error(msg)
            raise IOError(msg)

        lines = result.stdout.strip().split("\n")
        logger.debug(f"smartctl output: {lines}")
        if "NVMe" in result.stdout:
            # example_output
            # === START OF SMART DATA SECTION ===
            # SMART/Health Information (NVMe Log 0x02)
            # Critical Warning:                   0x00
            # Temperature:                        55 Celsius
            # Available Spare:                    100%
            metrics = {}
            # Parse NVMe SMART data
            for line in lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    metrics[key.strip()] = parse_smartctl_output(value.strip())
        else:
            # example line:
            #  ID# ATTRIBUTE_NAME          FLAG     VALUE WORST THRESH TYPE      UPDATED  WHEN_FAILED RAW_VALUE
            #   10 Spin_Retry_Count        0x0032   100   253   000    Old_age   Always       -       0
            metrics = {}
            for line in lines:
                tokens = line.split()
                if len(tokens) == 10 and tokens[2].startswith("0x"):
                    logger.debug(f"tokens: {tokens}")
                    key = tokens[1]
                    value = tokens[-1]
                    logger.debug(f"key: {key}, value: {value}")
                    metrics[key] = parse_smartctl_output(value)

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise
    return metrics


def get_disk_serials() -> Dict[str, str]:
    logger.info("probing system for list of disks")
    # Run lsblk command to get the serials of the disks
    result = subprocess.run(
        ["lsblk", "-o", "NAME,SERIAL"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Check if the command ran successfully
    if result.returncode != 0:
        msg = f"Error running lsblk: {result.stderr}"
        logger.error(msg)
        raise IOError(msg)
    # Parse the output
    lines = result.stdout.strip().split("\n")
    disks = {}

    for line in lines[1:]:  # Skip header
        parts = line.split()
        # example output:
        # sda    S598NJ0MC32609P
        # ├─sda1
        # └─sda2
        # sdb    WD-WMAY03561084
        if len(parts) == 2:
            disk, serial = parts
            disk = f"/dev/{disk}"
            disks[disk] = serial

    return disks


def get_disk_usage(partition_name) -> dict:
    try:
        result = subprocess.run(
            ["df", partition_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            raise IOError(f"Error running df: {result.stderr}")
    except Exception as e:
        raise IOError(f"An error occurred: {str(e)}")

    # example output:
    # Filesystem      1K-blocks      Used Available Use% Mounted on
    # /dev/sdb1      1441026652 439533320 928220092  33% /mnt/black1p5
    lines = result.stdout.strip().split("\n")
    fs, size, used, avail, pct, mntpt = lines[1].split()
    usage = {
        "filesystem": fs,
        "size": int(size),
        "used": int(used),
        "available": int(avail),
        "use_pct": int(pct[0:-1]),
        "mounted_on": mntpt,
    }
    return usage


def list_partitions(disk: str) -> List[str]:
    partitions = []
    for part in psutil.disk_partitions(all=False):
        if (
            part.device.startswith(disk)
            and part.fstype not in ["nfs", ""]
            and not part.device.startswith("/dev/mapper/")
        ):
            partitions.append(part.device)
    return list(set(partitions))


def all_drive_info():
    disks = get_disk_serials()
    pprint.pprint(disks)
    attributes_dict = {}
    now = (
        datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")
        + "Z"
    ).replace("+00:00", "")
    hostname = socket.gethostname()
    for disk, serial in disks.items():
        disk_state = get_disk_state(disk)
        if disk_state in RUNNING_STATES:
            logger.debug(f"Disk {disk} is running")
            smart_attributes = get_smart_attributes(disk)
            partitions = list_partitions(disk)
            logger.debug(f"for disk {disk}, Partitions: {partitions}")
            usage = [get_disk_usage(part) for part in partitions]
        else:
            logger.debug(f"Disk {disk} is not running")
            smart_attributes = None
            usage = None

        attributes = {
            "@timestamp": now,
            "serial": serial,
            "device": disk,
            "state": disk_state.value,
            "hostname": hostname,
        }
        if smart_attributes:
            attributes["smart_attributes"] = smart_attributes
        if usage:
            attributes["usage"] = usage

        attributes_dict[disk] = attributes
    return attributes_dict


from typing import List
import psutil


if __name__ == "__main__":
    attributes_dict = all_drive_info()
    pprint.pprint(attributes_dict)
