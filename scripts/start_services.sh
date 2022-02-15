docker run -p 5432:5432 -e POSTGRES_PASSWORD=password -v paperless_pgdata:/var/lib/postgresql/data -d postgres:13
docker run -d -p 6379:6379 redis:latest
docker run -p 3000:3000 -d thecodingmachine/gotenberg
docker run -p 9998:9998 -d apache/tika
