#!/usr/bin/env python3
"""
Part 1 Client: Reliable UDP File Transfer
Receives file with sliding window protocol and sends ACKs
"""

import socket
import sys
import time
import struct

# Constants
MAX_PAYLOAD = 1200
HEADER_SIZE = 20
DATA_SIZE = MAX_PAYLOAD - HEADER_SIZE
REQUEST_TIMEOUT = 2.0
MAX_RETRIES = 5

class ReliableUDPClient:
    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
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
        # ACK packet: 4 bytes ack_num + 16 bytes reserved (no data)
        return struct.pack('!I', ack_num) + b'\x00' * 16
    
    def send_request(self):
        """Send file request to server with retries"""
        request = b'G'  # Single byte request
        
        for attempt in range(MAX_RETRIES):
            try:
                print(f"Sending request (attempt {attempt + 1}/{MAX_RETRIES})...")
                self.sock.sendto(request, (self.server_ip, self.server_port))
                
                # Wait for first data packet
                self.sock.settimeout(REQUEST_TIMEOUT)
                data, _ = self.sock.recvfrom(MAX_PAYLOAD)
                
                if len(data) >= HEADER_SIZE:
                    print("Connection established!")
                    return data  # Return first packet
                    
            except socket.timeout:
                print(f"Timeout on attempt {attempt + 1}")
                continue
        
        print("Failed to connect after maximum retries")
        return None
    
    def receive_file(self, output_filename):
        """Receive file and write to output_filename"""
        print(f"Receiving file to {output_filename}...")
        
        # Send request and get first packet
        first_packet = self.send_request()
        if first_packet is None:
            return False
        
        # Set socket to non-blocking for receiving
        self.sock.settimeout(0.5)
        
        start_time = time.time()
        self.expected_seq = 0
        self.buffer = {}
        self.received_data = []
        
        # Process first packet
        packets_to_process = [first_packet]
        last_ack_time = time.time()
        consecutive_timeouts = 0
        
        while True:
            # Process any pending packets
            for packet in packets_to_process:
                seq_num, data = self.parse_packet(packet)
                
                if seq_num is None:
                    continue
                
                # Check for EOF
                if data == b'EOF':
                    print("Received EOF marker")
                    # Send final ACK
                    final_ack = self.create_ack(self.expected_seq)
                    for _ in range(5):
                        self.sock.sendto(final_ack, (self.server_ip, self.server_port))
                    
                    # Write received data to file
                    try:
                        with open(output_filename, 'wb') as f:
                            f.write(b''.join(self.received_data))
                        
                        duration = time.time() - start_time
                        total_bytes = sum(len(d) for d in self.received_data)
                        print(f"File received successfully: {total_bytes} bytes in {duration:.2f}s")
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
                    
                    # Check if we have buffered packets that can now be delivered
                    while self.expected_seq in self.buffer:
                        buffered_data = self.buffer.pop(self.expected_seq)
                        self.received_data.append(buffered_data)
                        self.expected_seq += len(buffered_data)
                    
                elif seq_num > self.expected_seq:
                    # Out-of-order packet - buffer it
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
            except socket.timeout:
                consecutive_timeouts += 1
                
                # Send duplicate ACK to prompt retransmission
                if time.time() - last_ack_time > 0.2:
                    ack = self.create_ack(self.expected_seq)
                    self.sock.sendto(ack, (self.server_ip, self.server_port))
                    last_ack_time = time.time()
                
                # If too many consecutive timeouts, assume transfer is done
                if consecutive_timeouts > 20:
                    print("Transfer appears to be complete (timeout)")
                    break
        
        return False
    
    def run(self):
        """Main client loop"""
        success = self.receive_file('received_data.txt')
        self.sock.close()
        
        if success:
            print("Client finished successfully")
        else:
            print("Client finished with errors")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 p1_client.py <SERVER_IP> <SERVER_PORT>")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    
    client = ReliableUDPClient(server_ip, server_port)
    client.run()

if __name__ == "__main__":
    main()
