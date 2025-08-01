#!/usr/bin/env python3
"""
Stream Diagnostics Tool
Helps identify causes of frame dropping in the microscope stream.
"""

import requests
import time
import json
from datetime import datetime

def get_stream_stats():
    """Get current streaming statistics from the API."""
    try:
        response = requests.get('http://localhost:5000/api/stream_stats', timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting stats: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return None

def get_status():
    """Get general system status."""
    try:
        response = requests.get('http://localhost:5000/api/status', timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting status: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return None

def monitor_stream(duration=60, interval=2):
    """
    Monitor streaming performance for a specified duration.
    
    Args:
        duration: Monitoring duration in seconds
        interval: Check interval in seconds
    """
    print(f"Starting stream monitoring for {duration} seconds...")
    print("=" * 60)
    
    start_time = time.time()
    last_stats = None
    total_drops = 0
    
    while time.time() - start_time < duration:
        current_time = time.time()
        
        # Get current status and stats
        status = get_status()
        stats = get_stream_stats()
        
        if status and status.get('stream_active'):
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Stream Active")
            
            if stats:
                target_fps = stats.get('target_fps', 0)
                actual_fps = stats.get('actual_fps', 0)
                drops = stats.get('frames_dropped', 0)
                queue_size = stats.get('queue_size', 0)
                queue_max = stats.get('queue_max_size', 0)
                
                # Calculate drop rate
                if last_stats:
                    new_drops = drops - last_stats.get('frames_dropped', 0)
                    total_drops += new_drops
                    drop_rate = new_drops / interval if interval > 0 else 0
                else:
                    drop_rate = 0
                
                # Calculate efficiency
                efficiency = (actual_fps / target_fps * 100) if target_fps > 0 else 0
                queue_usage = (queue_size / queue_max * 100) if queue_max > 0 else 0
                
                print(f"  Target FPS: {target_fps}")
                print(f"  Actual FPS: {actual_fps:.2f}")
                print(f"  Efficiency: {efficiency:.1f}%")
                print(f"  Frames Dropped: {drops} (Rate: {drop_rate:.1f}/sec)")
                print(f"  Queue Usage: {queue_size}/{queue_max} ({queue_usage:.1f}%)")
                
                # Warning indicators
                if efficiency < 90:
                    print(f"  ⚠️  Low efficiency: {efficiency:.1f}%")
                if queue_usage > 80:
                    print(f"  ⚠️  High queue usage: {queue_usage:.1f}%")
                if drop_rate > 1:
                    print(f"  ⚠️  High drop rate: {drop_rate:.1f} frames/sec")
                    
                last_stats = stats
            else:
                print("  ⚠️  Could not get detailed stats")
        else:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Stream Inactive")
        
        time.sleep(interval)
    
    # Summary
    print("\n" + "=" * 60)
    print("MONITORING SUMMARY")
    print("=" * 60)
    if last_stats:
        total_time = time.time() - start_time
        avg_fps = last_stats.get('actual_fps', 0)
        total_drops = last_stats.get('frames_dropped', 0)
        
        print(f"Monitoring Duration: {total_time:.1f} seconds")
        print(f"Average FPS: {avg_fps:.2f}")
        print(f"Total Frames Dropped: {total_drops}")
        print(f"Drop Rate: {total_drops/total_time:.2f} frames/sec")
        
        # Recommendations
        print("\nRECOMMENDATIONS:")
        if avg_fps < 13:
            print("- Consider reducing JPEG quality")
            print("- Check network bandwidth")
            print("- Reduce resolution if possible")
        if total_drops > 0:
            print("- Increase queue size")
            print("- Optimize image processing")
            print("- Check CPU usage")

def main():
    """Main diagnostic function."""
    print("Microscope Stream Diagnostics")
    print("=" * 60)
    
    # Check if server is running
    status = get_status()
    if not status:
        print("❌ Cannot connect to server. Make sure the Flask app is running.")
        return
    
    print("✅ Server connection successful")
    
    if not status.get('stream_active'):
        print("❌ Stream is not active. Start the stream first.")
        return
    
    print("✅ Stream is active")
    
    # Start monitoring
    try:
        monitor_stream(duration=60, interval=2)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")

if __name__ == "__main__":
    main() 