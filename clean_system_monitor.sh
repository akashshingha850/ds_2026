#!/bin/sh

# Stop and remove all containers using the system_monitor image
for cid in $(docker ps -a -q --filter ancestor=system_monitor); do
	docker stop "$cid" 2>/dev/null
	docker rm "$cid" 2>/dev/null
done

# Remove the image
docker rmi system_monitor
