docker build --platform=linux/amd64 --file Dockerfile --tag registry-dev.tcgroup.vn/tc-edoc:0.0.1 --progress simple .
docker push registry-dev.tcgroup.vn/tc-edoc:0.0.1
