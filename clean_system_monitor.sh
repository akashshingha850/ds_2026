#!/bin/sh
docker rm $(docker ps -a -q --filter ancestor=system_monitor) 2>/dev/null
docker rmi system_monitor
