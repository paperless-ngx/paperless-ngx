docker stop tc-edoc
docker run --rm --name tc-edoc -p 8000:8000 --env-file .env -v "$(pwd)/media:/usr/src/paperless/media" registry-dev.tcgroup.vn/tc-edoc:0.0.1
