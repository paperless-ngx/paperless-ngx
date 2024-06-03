#!/usr/bin/env bash

docker run -p 5432:5432 -e POSTGRES_PASSWORD=password -v paperless_pgdata:/var/lib/postgresql/data -d postgres:15
docker run -d -p 6379:6379 redis:latest
docker run -p 3000:3000 -d gotenberg/gotenberg:7.8 gotenberg --chromium-disable-javascript=true --chromium-allow-list="file:///tmp/.*"
docker run -p 9998:9998 -d docker.io/apache/tika:latest
