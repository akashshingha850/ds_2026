#!/bin/sh

docker run --rm --network host -v $(pwd)/logs:/app/logs -d system_monitor