import datetime
import socket
import pprint
import psutil
import GPUtil
import socket
import datetime


def get_cpu_usage():
    return psutil.cpu_percent(interval=1, percpu=True)


def get_memory_usage():
    mem = psutil.virtual_memory()
    return {"total": mem.total, "used": mem.used, "percent": mem.percent}


def get_gpu_usage():
    gpus = GPUtil.getGPUs()
    gpu_stats = []
    for gpu in gpus:
        gpu_stats.append(
            {
                "id": gpu.id,
                "name": gpu.name,
                "load": gpu.load * 100,
                "memory_total": gpu.memoryTotal,
                "memory_used": gpu.memoryUsed,
                "memory_free": gpu.memoryFree,
                "temperature": gpu.temperature,
            }
        )
    return gpu_stats


def cpu_memory_info():
    now = (
        datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")
        + "Z"
    ).replace("+00:00", "")
    cpu_usage = get_cpu_usage()
    memory_usage = get_memory_usage()
    gpu_usage = get_gpu_usage()
    data = {
        "@timestamp": now,
        "hostname": socket.gethostname(),
        "cpu_usage_pct": cpu_usage,
        "memory": memory_usage,
    }
    if gpu_usage:
        data["gpu"] = gpu_usage
    return data


if __name__ == "__main__":
    data = cpu_memory_info()
    pprint.pprint(data)
