@echo off
echo Installing QR Code Scanner Requirements...
echo.

pip install --upgrade pip
pip install opencv-python pyzbar pillow requests qrcode numpy

echo.
echo Installation complete!
echo Run the scanner with: python qrcode_scanner.py
pause