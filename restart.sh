#!/bin/bash

docker stop freqtrade
docker rm freqtrade
docker compose up -d
