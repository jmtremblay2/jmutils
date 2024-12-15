#!/usr/bin/python3

import diskstats
import requests
import json
import os

HOST = os.environ.get("ELASTICSEARCH_HOST", "localhost")
INDEX_NAME = os.environ.get("ELASTICSEARCH_DISKSTAT_INDEX", "diskhealth")

if __name__ == "__main__":
    attributes_dict = diskstats.all_drive_info()

    url = f"http://{HOST}:9200/{INDEX_NAME}/_doc"
    headers = {"Content-Type": "application/json"}

    for data in attributes_dict.values():
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code != 201:
            print(f"Error: {response.status_code}")
        else:
            print(f"Success: {response.json()}")
