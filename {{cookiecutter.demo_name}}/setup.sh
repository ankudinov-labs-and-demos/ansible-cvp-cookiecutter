#!/usr/bin/env bash

python3 -m venv .venv
source .venv/bin/activate
make install-requirements
make install