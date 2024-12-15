#!/usr/bin/python3

import cpustats
import requests
import json
import os

HOST = os.environ.get("ELASTICSEARCH_HOST", "localhost")
INDEX_NAME = os.environ.get("ELASTICSEARCH_CPUSTAT_INDEX", "cpuusage")

if __name__ == "__main__":
    attributes_dict = cpustats.cpu_memory_info()
    data = json.dumps(attributes_dict)
    url = f"http://{HOST}:9200/{INDEX_NAME}/_doc"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=data)
    if response.status_code != 201:
        print(f"Error: {response.status_code}")
    else:
        print(f"Success: {response.json()}")
