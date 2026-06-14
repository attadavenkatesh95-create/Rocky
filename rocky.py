"""
QR Code Scanner with Enhanced Tracking
Captures time, date, location, ISP, device info when scanning QR codes
Only requires: pip install opencv-python pyzbar pillow qrcode
"""

import cv2
import numpy as np
from pyzbar.pyzbar import decode
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from PIL import Image, ImageTk
import threading
import requests
import json
import csv
import os
from datetime import datetime
import socket
import platform
import uuid

CSV_FILE = "scanned_qrcodes_detailed.csv"

class QRScannerWithTracking:
    def __init__(self, root):
        self.root = root
        self.root.title("QR Code Scanner - Enhanced Tracking")
        self.root.geometry("1400x800")
        self.root.configure(bg='#1e1e2e')
        
        self.scanning = False
        self.camera = None
        self.scanned_data = []
        
        # Load existing data
        self.load_data()
        
        # Setup UI
        self.setup_ui()
        
        # Start camera
        self.start_camera()
        
        # Get device info once
        self.device_info = self.get_device_info()
        
    def get_device_info(self):
        """Get local device information"""
        return {
            'scanner_device': platform.node(),
            'scanner_os': platform.system(),
            'scanner_os_version': platform.version(),
            'scanner_machine': platform.machine(),
            'scanner_hostname': socket.gethostname()
        }
    
    def get_ip_info(self, ip=None):
        """Get detailed IP information"""
        try:
            if ip:
                response = requests.get(f'http://ip-api.com/json/{ip}', timeout=5)
            else:
                response = requests.get('http://ip-api.com/json/', timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {
                        'ip': data.get('query', 'N/A'),
                        'country': data.get('country', 'N/A'),
                        'country_code': data.get('countryCode', 'N/A'),
                        'region': data.get('regionName', 'N/A'),
                        'city': data.get('city', 'N/A'),
                        'zip': data.get('zip', 'N/A'),
                        'lat': data.get('lat', 'N/A'),
                        'lon': data.get('lon', 'N/A'),
                        'timezone': data.get('timezone', 'N/A'),
                        'isp': data.get('isp', 'N/A'),
                        'org': data.get('org', 'N/A'),
                        'as': data.get('as', 'N/A')
                    }
        except:
            pass
        return {
            'ip': 'Unable to fetch',
            'country': 'N/A', 'region': 'N/A', 'city': 'N/A',
            'isp': 'N/A', 'lat': 'N/A', 'lon': 'N/A'
        }
    
    def setup_ui(self):
        # Configure grid
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=2)
        self.root.grid_columnconfigure(1, weight=1)
        
        # Left Panel - Camera View
        left_panel = tk.Frame(self.root, bg='#2d2d3d', relief=tk.RAISED, bd=2)
        left_panel.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')
        
        # Camera title
        title_label = tk.Label(left_panel, text="📷 QR Code Scanner", 
                               font=('Arial', 18, 'bold'), 
                               bg='#2d2d3d', fg='#00d4ff')
        title_label.pack(pady=10)
        
        # Camera preview
        self.camera_label = tk.Label(left_panel, bg='#1e1e2e', 
                                     relief=tk.SUNKEN, bd=2)
        self.camera_label.pack(padx=10, pady=10, expand=True, fill='both')
        
        # Control buttons
        control_frame = tk.Frame(left_panel, bg='#2d2d3d')
        control_frame.pack(pady=10)
        
        self.scan_btn = tk.Button(control_frame, text="▶ Start Scanning", 
                                  command=self.toggle_scanning,
                                  font=('Arial', 12, 'bold'),
                                  bg='#00d4ff', fg='#1e1e2e',
                                  padx=20, pady=10, cursor='hand2')
        self.scan_btn.grid(row=0, column=0, padx=5)
        
        clear_btn = tk.Button(control_frame, text="🗑 Clear History", 
                              command=self.clear_history,
                              font=('Arial', 10),
                              bg='#ff4444', fg='white',
                              padx=15, pady=8, cursor='hand2')
        clear_btn.grid(row=0, column=1, padx=5)
        
        export_btn = tk.Button(control_frame, text="💾 Export CSV", 
                               command=self.export_csv,
                               font=('Arial', 10),
                               bg='#44ff44', fg='#1e1e2e',
                               padx=15, pady=8, cursor='hand2')
        export_btn.grid(row=0, column=2, padx=5)
        
        # Right Panel - Results
        right_panel = tk.Frame(self.root, bg='#2d2d3d', relief=tk.RAISED, bd=2)
        right_panel.grid(row=0, column=1, padx=10, pady=10, sticky='nsew')
        
        # Notebook for tabs
        notebook = ttk.Notebook(right_panel)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: Scanned Results
        results_frame = tk.Frame(notebook, bg='#2d2d3d')
        notebook.add(results_frame, text="📊 Scan History")
        
        # Treeview for results
        columns = ('#', 'Time', 'Date', 'QR Data', 'Type', 'Location', 'ISP', 'Device')
        self.tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.tree.heading(col, text=col)
            widths = {'#': 40, 'Time': 80, 'Date': 100, 'QR Data': 200, 
                     'Type': 80, 'Location': 150, 'ISP': 150, 'Device': 100}
            self.tree.column(col, width=widths.get(col, 100))
        
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill='y', pady=5)
        
        # Bind selection event
        self.tree.bind('<<TreeviewSelect>>', self.on_select_scan)
        
        # Tab 2: Detailed View
        detail_frame = tk.Frame(notebook, bg='#2d2d3d')
        notebook.add(detail_frame, text="📋 Scan Details")
        
        self.detail_text = scrolledtext.ScrolledText(detail_frame, font=('Courier', 10),
                                                      bg='#1e1e2e', fg='#00ff00',
                                                      wrap=tk.WORD)
        self.detail_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 3: Statistics
        stats_frame = tk.Frame(notebook, bg='#2d2d3d')
        notebook.add(stats_frame, text="📈 Statistics")
        
        self.stats_text = scrolledtext.ScrolledText(stats_frame, font=('Courier', 10),
                                                     bg='#1e1e2e', fg='#00ff00',
                                                     wrap=tk.WORD)
        self.stats_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Status bar
        status_frame = tk.Frame(self.root, bg='#1e1e2e')
        status_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=5)
        
        self.status_label = tk.Label(status_frame, text="Ready - Press Start Scanning", 
                                     bg='#1e1e2e', fg='#00d4ff', font=('Arial', 10))
        self.status_label.pack(side=tk.LEFT)
        
        self.scan_count_label = tk.Label(status_frame, text="Total Scans: 0", 
                                         bg='#1e1e2e', fg='white', font=('Arial', 10))
        self.scan_count_label.pack(side=tk.RIGHT)
        
        # Update display
        self.update_display()
        self.update_statistics()
    
    def load_data(self):
        """Load existing scan data from CSV"""
        if os.path.exists(CSV_FILE):
            try:
                with open(CSV_FILE, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    self.scanned_data = list(reader)
            except Exception as e:
                print(f"Error loading data: {e}")
                self.scanned_data = []
        else:
            self.scanned_data = []
    
    def save_scan_data(self, scan_info):
        """Save scan data to CSV with all tracking info"""
        file_exists = os.path.exists(CSV_FILE)
        
        fieldnames = [
            'scan_id', 'timestamp', 'date', 'time', 'qr_data', 'qr_type',
            'ip', 'country', 'country_code', 'region', 'city', 'zip',
            'latitude', 'longitude', 'timezone', 'isp', 'org', 'as_number',
            'device_type', 'os', 'browser', 'scanner_hostname', 'scanner_os'
        ]
        
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(scan_info)
        
        self.scanned_data.append(scan_info)
    
    def get_browser_info(self, user_agent):
        """Extract browser info from user agent"""
        if not user_agent:
            return "Unknown"
        
        ua = user_agent.lower()
        if 'chrome' in ua:
            return 'Chrome'
        elif 'firefox' in ua:
            return 'Firefox'
        elif 'safari' in ua:
            return 'Safari'
        elif 'edge' in ua:
            return 'Edge'
        elif 'opera' in ua:
            return 'Opera'
        else:
            return 'Other'
    
    def get_os_info(self, user_agent):
        """Extract OS info from user agent"""
        if not user_agent:
            return "Unknown"
        
        ua = user_agent.lower()
        if 'windows' in ua:
            return 'Windows'
        elif 'android' in ua:
            return 'Android'
        elif 'ios' in ua or 'iphone' in ua or 'ipad' in ua:
            return 'iOS'
        elif 'mac' in ua:
            return 'macOS'
        elif 'linux' in ua:
            return 'Linux'
        else:
            return 'Other'
    
    def get_device_type(self, user_agent):
        """Determine device type from user agent"""
        if not user_agent:
            return "Unknown"
        
        ua = user_agent.lower()
        if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
            return 'Mobile'
        elif 'tablet' in ua or 'ipad' in ua:
            return 'Tablet'
        else:
            return 'Desktop'
    
    def process_qr_data(self, qr_data):
        """Process scanned QR code with enhanced tracking"""
        timestamp = datetime.now()
        scan_id = str(uuid.uuid4())[:8]
        
        # Get IP and location info
        print("Fetching location data...")
        self.status_label.config(text="🌍 Fetching location data...")
        ip_info = self.get_ip_info()
        
        # Determine QR type
        qr_type = "URL" if qr_data.startswith(('http://', 'https://')) else "Text"
        
        # Get simulated user agent (since we can't get from webcam)
        # In a real web scenario, this would come from browser
        user_agent = f"Scanner Device - {platform.system()} {platform.release()}"
        
        # Compile all scan information
        scan_info = {
            'scan_id': scan_id,
            'timestamp': timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'date': timestamp.strftime("%Y-%m-%d"),
            'time': timestamp.strftime("%H:%M:%S"),
            'qr_data': qr_data,
            'qr_type': qr_type,
            'ip': ip_info.get('ip', 'N/A'),
            'country': ip_info.get('country', 'N/A'),
            'country_code': ip_info.get('country_code', 'N/A'),
            'region': ip_info.get('region', 'N/A'),
            'city': ip_info.get('city', 'N/A'),
            'zip': ip_info.get('zip', 'N/A'),
            'latitude': ip_info.get('lat', 'N/A'),
            'longitude': ip_info.get('lon', 'N/A'),
            'timezone': ip_info.get('timezone', 'N/A'),
            'isp': ip_info.get('isp', 'N/A'),
            'org': ip_info.get('org', 'N/A'),
            'as_number': ip_info.get('as', 'N/A'),
            'device_type': self.get_device_type(user_agent),
            'os': self.get_os_info(user_agent),
            'browser': self.get_browser_info(user_agent),
            'scanner_hostname': self.device_info.get('scanner_hostname', 'N/A'),
            'scanner_os': self.device_info.get('scanner_os', 'N/A')
        }
        
        # Check for duplicates (same QR code within 10 seconds)
        for existing in self.scanned_data:
            if (existing.get('qr_data') == qr_data and 
                abs((timestamp - datetime.strptime(existing['timestamp'], "%Y-%m-%d %H:%M:%S")).seconds) < 10):
                print("Duplicate scan ignored")
                self.status_label.config(text="⚠ Duplicate scan ignored")
                return
        
        # Save to CSV
        self.save_scan_data(scan_info)
        
        # Update displays
        self.update_display()
        self.update_statistics()
        
        # Show in detail view
        self.show_scan_details(scan_info)
        
        # Print to console
        print(f"\n{'='*60}")
        print(f"✅ QR Code Scanned!")
        print(f"{'='*60}")
        print(f"📅 Time: {scan_info['timestamp']}")
        print(f"📱 QR Data: {qr_data}")
        print(f"🔗 Type: {qr_type}")
        print(f"\n📍 LOCATION INFO:")
        print(f"   IP: {scan_info['ip']}")
        print(f"   Country: {scan_info['country']} ({scan_info['country_code']})")
        print(f"   City: {scan_info['city']}")
        print(f"   Region: {scan_info['region']}")
        print(f"   Coordinates: {scan_info['latitude']}, {scan_info['longitude']}")
        print(f"\n🌐 NETWORK INFO:")
        print(f"   ISP: {scan_info['isp']}")
        print(f"   Organization: {scan_info['org']}")
        print(f"   AS Number: {scan_info['as_number']}")
        print(f"\n💻 DEVICE INFO:")
        print(f"   Device Type: {scan_info['device_type']}")
        print(f"   OS: {scan_info['os']}")
        print(f"   Browser: {scan_info['browser']}")
        print(f"{'='*60}\n")
        
        self.status_label.config(text=f"✅ Scanned: {qr_data[:50]}... | Location: {scan_info['city']}, {scan_info['country']}")
        
        # Play beep
        self.root.bell()
        
        # Open URL if it's a link
        if qr_type == "URL":
            result = messagebox.askyesno("Open URL", f"Open this URL?\n\n{qr_data}")
            if result:
                import webbrowser
                webbrowser.open(qr_data)
    
    def show_scan_details(self, scan):
        """Show detailed information about a scan"""
        self.detail_text.delete(1.0, tk.END)
        
        details = f"""
╔══════════════════════════════════════════════════════════════════════╗
║                         SCAN DETAILS                                  ║
╠══════════════════════════════════════════════════════════════════════╣
║ Scan ID: {scan['scan_id']}
║ Date & Time: {scan['timestamp']}
╠══════════════════════════════════════════════════════════════════════╣
║ QR CODE INFORMATION
╠══════════════════════════════════════════════════════════════════════╣
║ Type: {scan['qr_type']}
║ Data: {scan['qr_data']}
╠══════════════════════════════════════════════════════════════════════╣
║ LOCATION INFORMATION
╠══════════════════════════════════════════════════════════════════════╣
║ IP Address: {scan['ip']}
║ Country: {scan['country']} ({scan['country_code']})
║ Region: {scan['region']}
║ City: {scan['city']}
║ Postal Code: {scan['zip']}
║ Coordinates: {scan['latitude']}, {scan['longitude']}
║ Timezone: {scan['timezone']}
╠══════════════════════════════════════════════════════════════════════╣
║ NETWORK INFORMATION
╠══════════════════════════════════════════════════════════════════════╣
║ ISP: {scan['isp']}
║ Organization: {scan['org']}
║ AS Number: {scan['as_number']}
╠══════════════════════════════════════════════════════════════════════╣
║ DEVICE INFORMATION
╠══════════════════════════════════════════════════════════════════════╣
║ Device Type: {scan['device_type']}
║ Operating System: {scan['os']}
║ Browser: {scan['browser']}
║ Scanner Device: {scan['scanner_hostname']}
║ Scanner OS: {scan['scanner_os']}
╚══════════════════════════════════════════════════════════════════════╝
"""
        self.detail_text.insert(1.0, details)
    
    def on_select_scan(self, event):
        """Handle selection of a scan from the list"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            values = item['values']
            if len(values) > 0:
                # Find the scan data
                scan_id = int(values[0]) - 1
                if 0 <= scan_id < len(self.scanned_data):
                    self.show_scan_details(self.scanned_data[scan_id])
    
    def update_display(self):
        """Update the treeview with scan data"""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add scans
        for idx, scan in enumerate(reversed(self.scanned_data), 1):
            location = f"{scan.get('city', 'N/A')}, {scan.get('country', 'N/A')}"
            if location == "N/A, N/A":
                location = "Unknown"
            
            qr_data_short = scan['qr_data'][:40] + '...' if len(scan['qr_data']) > 40 else scan['qr_data']
            
            self.tree.insert('', 'end', values=(
                idx,
                scan.get('time', 'N/A'),
                scan.get('date', 'N/A'),
                qr_data_short,
                scan.get('qr_type', 'N/A'),
                location,
                scan.get('isp', 'N/A')[:30],
                scan.get('device_type', 'N/A')
            ))
        
        self.scan_count_label.config(text=f"Total Scans: {len(self.scanned_data)}")
    
    def update_statistics(self):
        """Update statistics tab"""
        self.stats_text.delete(1.0, tk.END)
        
        if not self.scanned_data:
            self.stats_text.insert(tk.END, "No scans yet. Start scanning QR codes to see statistics!")
            return
        
        # Calculate statistics
        unique_ips = set()
        unique_countries = set()
        unique_cities = set()
        unique_isps = set()
        device_types = {}
        qr_types = {}
        os_types = {}
        
        for scan in self.scanned_data:
            if scan.get('ip'):
                unique_ips.add(scan['ip'])
            if scan.get('country'):
                unique_countries.add(scan['country'])
            if scan.get('city'):
                unique_cities.add(scan['city'])
            if scan.get('isp'):
                unique_isps.add(scan['isp'])
            
            device = scan.get('device_type', 'Unknown')
            device_types[device] = device_types.get(device, 0) + 1
            
            qr_type = scan.get('qr_type', 'Unknown')
            qr_types[qr_type] = qr_types.get(qr_type, 0) + 1
            
            os_type = scan.get('os', 'Unknown')
            os_types[os_type] = os_types.get(os_type, 0) + 1
        
        stats = f"""
╔══════════════════════════════════════════════════════════════════════╗
║                         SCAN STATISTICS                               ║
╠══════════════════════════════════════════════════════════════════════╣
║ TOTAL STATISTICS
╠══════════════════════════════════════════════════════════════════════╣
║ Total Scans:           {len(self.scanned_data)}
║ Unique IPs:            {len(unique_ips)}
║ Unique Countries:      {len(unique_countries)}
║ Unique Cities:         {len(unique_cities)}
║ Unique ISPs:           {len(unique_isps)}
╠══════════════════════════════════════════════════════════════════════╣
║ DEVICE TYPE BREAKDOWN
╠══════════════════════════════════════════════════════════════════════╣
"""
        for device, count in device_types.items():
            percentage = (count / len(self.scanned_data)) * 100
            stats += f"║ {device:<15} : {count:>4} scans ({percentage:>5.1f}%)\n"
        
        stats += f"""╠══════════════════════════════════════════════════════════════════════╣
║ QR CODE TYPE BREAKDOWN
╠══════════════════════════════════════════════════════════════════════╣
"""
        for qr_type, count in qr_types.items():
            percentage = (count / len(self.scanned_data)) * 100
            stats += f"║ {qr_type:<15} : {count:>4} scans ({percentage:>5.1f}%)\n"
        
        stats += f"""╠══════════════════════════════════════════════════════════════════════╣
║ OPERATING SYSTEM BREAKDOWN
╠══════════════════════════════════════════════════════════════════════╣
"""
        for os_type, count in os_types.items():
            percentage = (count / len(self.scanned_data)) * 100
            stats += f"║ {os_type:<15} : {count:>4} scans ({percentage:>5.1f}%)\n"
        
        stats += f"""╠══════════════════════════════════════════════════════════════════════╣
║ TOP LOCATIONS
╠══════════════════════════════════════════════════════════════════════╣
"""
        # Show top 5 countries
        country_counts = {}
        for scan in self.scanned_data:
            country = scan.get('country', 'Unknown')
            country_counts[country] = country_counts.get(country, 0) + 1
        
        sorted_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        for country, count in sorted_countries:
            stats += f"║ {country:<30} : {count} scans\n"
        
        stats += "╚══════════════════════════════════════════════════════════════════════╝"
        
        self.stats_text.insert(1.0, stats)
    
    def start_camera(self):
        """Initialize camera"""
        try:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                self.status_label.config(text="⚠ Camera not found!")
                return
            self.update_camera_feed()
        except Exception as e:
            self.status_label.config(text=f"Camera error: {str(e)}")
    
    def update_camera_feed(self):
        """Update camera feed in GUI"""
        if self.camera and self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret:
                # QR Code detection
                if self.scanning:
                    qr_codes = decode(frame)
                    for qr in qr_codes:
                        qr_data = qr.data.decode('utf-8')
                        self.process_qr_data(qr_data)
                        
                        # Draw rectangle around QR code
                        points = qr.polygon
                        if len(points) == 4:
                            pts = np.array([(point.x, point.y) for point in points], np.int32)
                            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
                        
                        # Put text
                        cv2.putText(frame, qr_data[:30], (qr.rect.left, qr.rect.top - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Convert to RGB for tkinter
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                img_tk = ImageTk.PhotoImage(img)
                
                self.camera_label.config(image=img_tk)
                self.camera_label.image = img_tk
            
            # Schedule next update
            self.root.after(30, self.update_camera_feed)
    
    def toggle_scanning(self):
        """Start/stop scanning"""
        self.scanning = not self.scanning
        if self.scanning:
            self.scan_btn.config(text="⏸ Stop Scanning", bg='#ff4444')
            self.status_label.config(text="🔍 Scanning for QR codes...")
        else:
            self.scan_btn.config(text="▶ Start Scanning", bg='#00d4ff')
            self.status_label.config(text="Scanning paused")
    
    def clear_history(self):
        """Clear all scan history"""
        if messagebox.askyesno("Confirm", "Are you sure you want to clear ALL scan history?"):
            self.scanned_data = []
            if os.path.exists(CSV_FILE):
                os.remove(CSV_FILE)
            self.update_display()
            self.update_statistics()
            self.detail_text.delete(1.0, tk.END)
            self.status_label.config(text="History cleared")
            messagebox.showinfo("Success", "All scan history has been cleared")
    
    def export_csv(self):
        """Export data to CSV"""
        if not self.scanned_data:
            messagebox.showwarning("Warning", "No data to export")
            return
        
        filename = f"qr_scans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            import shutil
            shutil.copy(CSV_FILE, filename)
            messagebox.showinfo("Success", f"Data exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {str(e)}")
    
    def on_closing(self):
        """Clean up on close"""
        if self.camera:
            self.camera.release()
        self.root.destroy()

def main():
    # Check for required libraries
    missing = []
    try:
        import cv2
    except ImportError:
        missing.append('opencv-python')
    
    try:
        from pyzbar.pyzbar import decode
    except ImportError:
        missing.append('pyzbar')
    
    if missing:
        print("Missing required libraries. Please install:")
        print(f"pip install {' '.join(missing)} requests pillow qrcode")
        input("\nPress Enter to exit...")
        return
    
    root = tk.Tk()
    app = QRScannerWithTracking(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    print("="*60)
    print("   QR Code Scanner with Enhanced Tracking")
    print("="*60)
    print("\nThis scanner captures detailed information when scanning QR codes:")
    print("  • Date & Time of scan")
    print("  • IP Address & Location (Country, City, Region)")
    print("  • ISP Information")
    print("  • Device Type, OS, Browser")
    print("  • GPS Coordinates")
    print("="*60 + "\n")
    
    main()
