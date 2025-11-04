#!/usr/bin/env python3
"""
Part 2 Client: Reliable UDP File Transfer with Congestion Control
Receives file and sends ACKs
"""

import socket
import sys
import time
import struct
import os

# Constants
MAX_PAYLOAD = 1200
HEADER_SIZE = 20
DATA_SIZE = MAX_PAYLOAD - HEADER_SIZE
REQUEST_TIMEOUT = 2.0
MAX_RETRIES = 5

class CongestionControlClient:
    def __init__(self, server_ip, server_port, pref_filename):
        self.server_ip = server_ip
        self.server_port = server_port
        self.pref_filename = pref_filename
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(REQUEST_TIMEOUT)
        
        # Receive buffer
        self.expected_seq = 0
        self.buffer = {}  # seq_num -> data (for out-of-order packets)
        self.received_data = []
        
        print(f"Client connecting to {self.server_ip}:{self.server_port}")
    
    def parse_packet(self, packet):
        """Parse packet to extract seq_num and data"""
        if len(packet) < HEADER_SIZE:
            return None, None
        
        seq_num = struct.unpack('!I', packet[:4])[0]
        data = packet[HEADER_SIZE:]
        return seq_num, data
    
    def create_ack(self, ack_num):
        """Create ACK packet"""
        return struct.pack('!I', ack_num) + b'\x00' * 16
    
    def send_request(self):
        """Send file request to server with retries"""
        request = b'G'
        
        for attempt in range(MAX_RETRIES):
            try:
                print(f"Sending request (attempt {attempt + 1}/{MAX_RETRIES})...")
                self.sock.sendto(request, (self.server_ip, self.server_port))
                
                self.sock.settimeout(REQUEST_TIMEOUT)
                data, _ = self.sock.recvfrom(MAX_PAYLOAD)
                
                if len(data) >= HEADER_SIZE:
                    print("Connection established!")
                    return data
                    
            except socket.timeout:
                print(f"Timeout on attempt {attempt + 1}")
                continue
        
        print("Failed to connect after maximum retries")
        return None
    
    def receive_file(self, output_filename):
        """Receive file and write to output_filename"""
        print(f"Receiving file to {output_filename}...")
        
        first_packet = self.send_request()
        if first_packet is None:
            return False
        
        self.sock.settimeout(0.5)
        
        start_time = time.time()
        self.expected_seq = 0
        self.buffer = {}
        self.received_data = []
        
        packets_to_process = [first_packet]
        last_ack_time = time.time()
        consecutive_timeouts = 0
        last_progress_time = time.time()
        
        while True:
            # Process pending packets
            for packet in packets_to_process:
                seq_num, data = self.parse_packet(packet)
                
                if seq_num is None:
                    continue
                
                # Check for EOF
                if data == b'EOF':
                    print("\nReceived EOF marker")
                    final_ack = self.create_ack(self.expected_seq)
                    for _ in range(5):
                        self.sock.sendto(final_ack, (self.server_ip, self.server_port))
                    
                    try:
                        with open(output_filename, 'wb') as f:
                            f.write(b''.join(self.received_data))
                        
                        duration = time.time() - start_time
                        total_bytes = sum(len(d) for d in self.received_data)
                        print(f"File received successfully: {total_bytes} bytes")
                        print(f"Duration: {duration:.2f}s")
                        print(f"Throughput: {(total_bytes * 8 / duration / 1_000_000):.2f} Mbps")
                        return True
                    except Exception as e:
                        print(f"Error writing file: {e}")
                        return False
                
                # Handle data packet
                if seq_num == self.expected_seq:
                    # In-order packet
                    self.received_data.append(data)
                    self.expected_seq += len(data)
                    
                    # Deliver buffered packets
                    while self.expected_seq in self.buffer:
                        buffered_data = self.buffer.pop(self.expected_seq)
                        self.received_data.append(buffered_data)
                        self.expected_seq += len(buffered_data)
                    
                elif seq_num > self.expected_seq:
                    # Out-of-order packet
                    if seq_num not in self.buffer:
                        self.buffer[seq_num] = data
                
                # Send cumulative ACK
                ack = self.create_ack(self.expected_seq)
                self.sock.sendto(ack, (self.server_ip, self.server_port))
                last_ack_time = time.time()
            
            packets_to_process = []
            
            # Try to receive more packets
            try:
                packet, _ = self.sock.recvfrom(MAX_PAYLOAD)
                packets_to_process.append(packet)
                consecutive_timeouts = 0
                
                # Progress indicator
                if time.time() - last_progress_time > 2.0:
                    received_mb = sum(len(d) for d in self.received_data) / (1024 * 1024)
                    print(f"Received: {received_mb:.2f} MB")
                    last_progress_time = time.time()
                    
            except socket.timeout:
                consecutive_timeouts += 1
                
                # Send duplicate ACK
                if time.time() - last_ack_time > 0.2:
                    ack = self.create_ack(self.expected_seq)
                    self.sock.sendto(ack, (self.server_ip, self.server_port))
                    last_ack_time = time.time()
                
                if consecutive_timeouts > 20:
                    print("\nTransfer appears complete (timeout)")
                    break
        
        return False
    
    def run(self):
        """Main client loop"""
        output_filename = f"{self.pref_filename}received_data.txt"
        success = self.receive_file(output_filename)
        self.sock.close()
        
        if success:
            print("Client finished successfully")
        else:
            print("Client finished with errors")

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 p2_client.py <SERVER_IP> <SERVER_PORT> <PREF_FILENAME>")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    pref_filename = sys.argv[3]
    
    client = CongestionControlClient(server_ip, server_port, pref_filename)
    client.run()

if __name__ == "__main__":
    main()
