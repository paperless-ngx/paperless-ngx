docker stop tc-edoc
docker run --rm --name tc-edoc -p 8000:8000 --env-file .env  registry-dev.tcgroup.vn/tc-edoc:0.0.1
