#!/bin/bash
echo "Installing QR Code Scanner Requirements..."

pip3 install --upgrade pip
pip3 install opencv-python pyzbar pillow requests qrcode numpy

echo ""
echo "Installation complete!"
echo "Run the scanner with: python3 qrcode_scanner.py"