#!/bin/bash

# && sudo chmod +x setup.sh && ./setup.sh -i

# 2. Activate virtual environment

# ```
# source ./.venv/bin/activate
# ```

##
# Python
##
sudo apt update
sudo apt install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev \
    libnss3-dev libssl-dev libreadline-dev libffi-dev curl libsqlite3-dev

cd /usr/src
sudo curl -O https://www.python.org/ftp/python/3.10.12/Python-3.10.12.tgz
sudo tar -xf Python-3.10.12.tgz
cd Python-3.10.12
sudo ./configure --enable-optimizations
sudo make -j $(nproc)
sudo make altinstall

alias python3 = python3.10
alias python = python3

##
# Docker & Docker compose
##
sudo apt-get update -y
sudo apt-get install \
ca-certificates \
curl \
gnupg \
lsb-release -y
sudo mkdir -m 0755 -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
$(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
sudo apt install docker-compose -y
