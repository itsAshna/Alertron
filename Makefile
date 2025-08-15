train:
\tpython model/train.py

build:
\tdocker compose build

up:
\tdocker compose up -d

logs:
\tdocker compose logs -f anomaly-service prometheus alertmanager traffic-gen

down:
\tdocker compose down -v
