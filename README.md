# jmutils


# install virtual environment 
```bash
# install virtual environment + requirement
python3 -m venv diskvenv
source diskvenv/bin/activate
pip install -r requirements
```

# Diskstats / cpustats
```bash
# list your disk stats
python diskstats.py
# publish to elasticsearch
ELASTICSEARCH_HOST=192.168.1.23 python diskpublish.py

# list your cpu/memory/gpustats
python cpustats.py
# publish to elasticsearch
ELASTICSEARCH_HOST=192.168.1.23 python cpupublish.py



```