#!/bin/bash

# install packages
sudo apt-get update
sudo apt-get build-dep -y python-imaging
sudo apt-get install -y libjpeg8 libjpeg62-dev libfreetype6 libfreetype6-dev
sudo apt-get install -y build-essential python3-dev python3-pip sqlite3 libsqlite3-dev git

# setup python project
pushd /opt/paperless
sudo pip3 install -r requirements.txt
popd
