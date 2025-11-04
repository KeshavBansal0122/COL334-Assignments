#!/usr/bin/env python3
"""
Part 1 Server: Reliable UDP File Transfer
Implements sliding window protocol with ACKs, timeouts, and fast retransmit
"""

import socket
import sys
import time
import struct
import os
import logging

# Constants
MAX_PAYLOAD = 1200
HEADER_SIZE = 20
DATA_SIZE = MAX_PAYLOAD - HEADER_SIZE  # 1180 bytes
INITIAL_TIMEOUT = 1.0
ALPHA = 1/8
BETA = 1/4
K = 4

class ReliableUDPServer:
    def __init__(self, server_ip, server_port, sws):
        self.server_ip = server_ip
        self.server_port = server_port
        self.sws = sws  # Sender Window Size in bytes
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.server_ip, self.server_port))
        
        # Setup logging
        self.setup_logging()
        
        # RTT estimation
        self.estimated_rtt = -1
        self.dev_rtt = 0
        self.rto = INITIAL_TIMEOUT
        
        # Window management
        self.base = 0  # First unacknowledged byte
        self.next_seq = 0  # Next byte to send
        self.packets = {}  # seq_num -> (data, send_time)
        self.dup_ack_count = {}  # ack_num -> count
        
        self.logger.info(f"Server listening on {self.server_ip}:{self.server_port}")
        self.logger.info(f"Sender Window Size: {self.sws} bytes")
        print(f"Server listening on {self.server_ip}:{self.server_port}")
        print(f"Sender Window Size: {self.sws} bytes")
    
    def setup_logging(self):
        """Setup file-based logging"""
        log_file = 'server.log'
        # Clear previous log file if it exists
        if os.path.exists(log_file):
            open(log_file, 'w').close()
        
        self.logger = logging.getLogger('ReliableUDPServer')
        self.logger.setLevel(logging.DEBUG)
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Formatter with timestamp
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', 
                                     datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
    
    def create_packet(self, seq_num, data):
        """Create a packet with header and data"""
        # Header: 4 bytes seq_num + 16 bytes reserved
        header = struct.pack('!I', seq_num) + b'\x00' * 16
        return header + data
    
    def parse_ack(self, packet):
        """Parse ACK packet to get ack number"""
        if len(packet) < 4:
            return None
        ack_num = struct.unpack('!I', packet[:4])[0]
        return ack_num
    
    def update_rtt(self, sample_rtt):
        """Update RTT estimates using TCP-like algorithm"""
        if self.estimated_rtt == -1:
            self.estimated_rtt = sample_rtt
            self.dev_rtt = sample_rtt/2
            self.rto = sample_rtt*1.5
            return
        
        self.estimated_rtt = (1 - ALPHA) * self.estimated_rtt + ALPHA * sample_rtt
        self.dev_rtt = (1 - BETA) * self.dev_rtt + BETA * abs(sample_rtt - self.estimated_rtt)
        self.rto = self.estimated_rtt + K * self.dev_rtt
        # self.rto = max(0.1, min(self.rto, 2.0))  # Clamp between 0.1 and 2 seconds
        self.rto = max(.1, self.rto)
    
    def send_file(self, client_addr, filename):
        """Send file using sliding window protocol"""
        try:
            with open(filename, 'rb') as f:
                file_data = f.read()
        except FileNotFoundError:
            print(f"Error: File {filename} not found")
            self.logger.error(f"Error: File {filename} not found")
            return
        
        total_bytes = len(file_data)
        print(f"Starting file transfer: {total_bytes} bytes")
        self.logger.info(f"Starting file transfer: {total_bytes} bytes")
        
        # Set socket to non-blocking
        self.sock.settimeout(0.001)
        
        start_time = time.time()
        self.base = 0
        self.next_seq = 0
        self.packets = {}
        self.dup_ack_count = {}
        
        # Split file into chunks
        chunks = []
        for i in range(0, total_bytes, DATA_SIZE):
            chunks.append(file_data[i:i + DATA_SIZE])
        
        total_packets = len(chunks)
        print(f"Total packets to send: {total_packets}")
        self.logger.info(f"Total packets to send: {total_packets}")
        
        while self.base < total_bytes:
            # Send new packets within window
            while self.next_seq < total_bytes and (self.next_seq - self.base) < self.sws:
                chunk_idx = self.next_seq // DATA_SIZE
                if chunk_idx < len(chunks):
                    data = chunks[chunk_idx]
                    packet = self.create_packet(self.next_seq, data)
                    self.sock.sendto(packet, client_addr)
                    self.logger.debug(f"SEND: seq={self.next_seq} size={len(data)} bytes")
                    self.packets[self.next_seq] = (packet, time.time())
                    self.next_seq += len(data)
            
            # Try to receive ACKs
            try:
                ack_packet, _ = self.sock.recvfrom(MAX_PAYLOAD)
                ack_num = self.parse_ack(ack_packet)
                self.logger.debug(f"RECV ACK: ack_num={ack_num}")
                
                if ack_num is not None and ack_num > self.base:
                    # Cumulative ACK - all bytes up to ack_num-1 received
                    if self.base in self.packets:
                        _, send_time = self.packets[self.base]
                        sample_rtt = time.time() - send_time
                        self.update_rtt(sample_rtt)
                    
                    # Remove acknowledged packets
                    acked_seqs = [seq for seq in self.packets if seq < ack_num]
                    for seq in acked_seqs:
                        del self.packets[seq]
                    
                    self.base = ack_num
                    self.dup_ack_count = {}  # Reset duplicate ACK counter
                    self.logger.info(f"Recieved ack: {ack_num}, new rto: {self.rto}")
                    
                elif ack_num is not None and ack_num == self.base:
                    # Duplicate ACK
                    self.dup_ack_count[ack_num] = self.dup_ack_count.get(ack_num, 0) + 1
                    
                    # Fast retransmit after 3 duplicate ACKs
                    if self.dup_ack_count[ack_num] == 3:
                        if self.base in self.packets:
                            packet, _ = self.packets[self.base]
                            self.sock.sendto(packet, client_addr)
                            self.packets[self.base] = (packet, time.time())
                            self.logger.warning(f"Fast retransmit: seq {self.base}")
                            print(f"Fast retransmit: seq {self.base}")
            
            except socket.timeout:
                pass
            
            # Check for timeouts
            current_time = time.time()
            for seq_num in list(self.packets.keys()):
                packet, send_time = self.packets[seq_num]
                if current_time - send_time > self.rto:
                    # Timeout - retransmit
                    self.sock.sendto(packet, client_addr)
                    self.packets[seq_num] = (packet, current_time)
                    self.logger.warning(f"TIMEOUT retransmit: seq={seq_num} RTO={self.rto:.3f}s")
                    print(f"Timeout retransmit: seq {seq_num}, RTO: {self.rto:.3f}s")
                    break  # Only retransmit one packet per timeout
        
        # Send EOF marker
        eof_packet = self.create_packet(self.next_seq, b'EOF')
        for _ in range(5):  # Send EOF multiple times to ensure delivery
            self.sock.sendto(eof_packet, client_addr)
            self.logger.debug("SEND: EOF marker")
            time.sleep(0.1)
        
        duration = time.time() - start_time
        print(f"File transfer complete in {duration:.2f} seconds")
        print(f"Throughput: {(total_bytes * 8 / duration / 1_000_000):.2f} Mbps")
        self.logger.info(f"File transfer complete in {duration:.2f} seconds")
        self.logger.info(f"Throughput: {(total_bytes * 8 / duration / 1_000_000):.2f} Mbps")
    
    def run(self):
        """Main server loop"""
        print("Waiting for client request...")
        self.logger.info("Server started - waiting for client request")
        
        while True:
            try:
                data, client_addr = self.sock.recvfrom(MAX_PAYLOAD)
                if len(data) > 0:
                    print(f"Received request from {client_addr}")
                    self.logger.info(f"Received request from {client_addr}")
                    self.send_file(client_addr, 'data.txt')
                    break
            except KeyboardInterrupt:
                print("\nServer shutting down")
                self.logger.info("Server shutting down")
                break
        
        self.sock.close()

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 p1_server.py <SERVER_IP> <SERVER_PORT> <SWS>")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    sws = int(sys.argv[3])
    
    server = ReliableUDPServer(server_ip, server_port, sws)
    server.run()

if __name__ == "__main__":
    main()
