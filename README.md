# Rocky
# 📱 QR Code Scanner with Enhanced Tracking

A powerful QR code scanner that captures detailed information about each scan including location, ISP, device info, and more.

## ✨ Features

- **Real-time QR Code Scanning** using webcam
- **Location Tracking** - Country, City, Region, GPS coordinates
- **Network Info** - IP Address, ISP, Organization
- **Device Detection** - Device type, OS, Browser
- **Time Tracking** - Exact date and time of each scan
- **Data Export** - Save all scans to CSV
- **Statistics Dashboard** - View scan analytics
- **Detailed History** - Complete scan records

## 📋 Captured Information

Each scan captures:
- 🕐 Date & Time
- 📍 Location (Country, City, Region)
- 🌐 IP Address & ISP
- 💻 Device Type & OS
- 🔍 QR Code Content

## 🚀 Quick Start

### Installation

1. **Install Python** (3.8 or higher)

2. **Install requirements:**
```bash
pip install -r requirements.txt

📊 Data Format

CSV includes: timestamp, date, time, qr_data, qr_type, ip, country, city, region, latitude, longitude, isp, device_type, os, browser, and more.

⚠️ Note

This tool captures IP and location data. Use responsibly and in compliance with privacy laws.
