#!/bin/bash

sudo apt update
sudo apt install -y python3-venv

python3 -m venv bankenv

source bankenv/bin/activate
pip install PyQt6 matplotlib pandas

