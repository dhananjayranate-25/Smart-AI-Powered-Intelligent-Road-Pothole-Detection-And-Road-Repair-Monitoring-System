#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing CPU-only PyTorch..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

echo "Installing remaining requirements..."
pip install -r requirements.txt
