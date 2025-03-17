#!/bin/bash

IMAGE_NAME="otxtan/tc-edoc"

# Lọc chỉ những tag hợp lệ dạng x.y.z
versions=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "$IMAGE_NAME" | cut -d ':' -f2 | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V)

# Lấy version mới nhất
current_version=$(echo "$versions" | tail -n 1)

if [ -z "$current_version" ]; then
    current_version="0.0.0"
fi

IFS='.' read -r major minor patch <<< "$current_version"

# Tăng patch
patch=$((patch + 1))

# Nếu patch > 9, tăng minor
if [ "$patch" -gt 9 ]; then
    patch=0
    minor=$((minor + 1))
    if [ "$minor" -gt 9 ]; then
        minor=0
        major=$((major + 1))
    fi
fi

new_version="${major}.${minor}.${patch}"

echo "🔢 Current version: $current_version"
echo "🚀 New version: $new_version"

docker build --file Dockerfile --tag ${IMAGE_NAME}:${new_version} --progress plain .
docker push otxtan/tc-edoc:${new_version}
