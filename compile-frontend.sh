#!/bin/bash

set -e

cd src-ui
npm install
./node_modules/.bin/ng build --prod
