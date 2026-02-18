#!/bin/sh

docker run --rm --network host -v $(pwd)/logs:/app/logs --name system_monitor -d system_monitor