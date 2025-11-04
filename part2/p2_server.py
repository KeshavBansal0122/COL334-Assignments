#!/usr/bin/env python3
"""
Part 2 Server: Reliable UDP File Transfer with Congestion Control
Implements TCP Reno-like congestion control with sliding window protocol
"""

import socket
import sys
import time
import struct
import os
import math

# Constants
MAX_PAYLOAD = 1200
HEADER_SIZE = 20
DATA_SIZE = MAX_PAYLOAD - HEADER_SIZE  # 1180 bytes (MSS)
MSS = DATA_SIZE
INITIAL_TIMEOUT = 1.0
ALPHA = 0.125
BETA = 0.25
K = 4
INITIAL_SSTHRESH = 128 * MSS  # Allow slow start to probe multi-MB BDP paths

class CongestionControlServer:
    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.server_ip, self.server_port))
        
        # RTT estimation
        self.estimated_rtt = INITIAL_TIMEOUT
        self.dev_rtt = 0
        self.rto = INITIAL_TIMEOUT
        
        # Congestion control state
        self.cwnd = MSS  # Congestion window (starts at 1 MSS)
        self.ssthresh = INITIAL_SSTHRESH  # Slow start threshold
        self.in_slow_start = True
        self.bytes_acked_in_rtt = 0
        
        # Window management
        self.base = 0  # First unacknowledged byte
        self.next_seq = 0  # Next byte to send
        self.packets = {}  # seq_num -> (data, send_time)
        self.dup_ack_count = {}  # ack_num -> count
        self.last_ack = 0
        self.in_fast_recovery = False
        self.recover = 0
        
        # Statistics
        self.cwnd_log = []  # For debugging
        self.time_start = 0
        
        print(f"Server listening on {self.server_ip}:{self.server_port}")
        print(f"Initial cwnd: {self.cwnd} bytes ({self.cwnd/MSS:.1f} MSS)")
    
    def create_packet(self, seq_num, data):
        """Create a packet with header and data"""
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
        self.estimated_rtt = (1 - ALPHA) * self.estimated_rtt + ALPHA * sample_rtt
        self.dev_rtt = (1 - BETA) * self.dev_rtt + BETA * abs(sample_rtt - self.estimated_rtt)
        self.rto = self.estimated_rtt + K * self.dev_rtt
        self.rto = max(0.3, min(self.rto, 3.0))
    
    def on_new_ack(self, acked_bytes):
        """Handle new ACK and update congestion window (TCP Reno)"""
        if self.in_slow_start:
            # Slow start: increase cwnd by MSS for each ACK
            self.cwnd += MSS
            if self.cwnd >= self.ssthresh:
                self.in_slow_start = False
                print(f"Exiting slow start: cwnd={self.cwnd/MSS:.1f} MSS, ssthresh={self.ssthresh/MSS:.1f} MSS")
        else:
            # Congestion avoidance: increase cwnd by roughly MSS per RTT
            # Standard TCP: cwnd += MSS * MSS / cwnd per ACK
            # Slightly more aggressive for better utilization on high-delay paths
            increment = (MSS * MSS) / self.cwnd
            self.cwnd += increment
        
        # Log cwnd for analysis
        if time.time() - self.time_start > 0:
            self.cwnd_log.append((time.time() - self.time_start, self.cwnd / MSS))
    
    def on_timeout(self):
        """Handle timeout event (TCP Reno)"""
        print(f"Timeout! cwnd: {self.cwnd/MSS:.1f} -> 1 MSS, ssthresh: {self.ssthresh/MSS:.1f} -> {self.cwnd/(2*MSS):.1f} MSS")
        self.ssthresh = max(self.cwnd // 2, 2 * MSS)
        self.cwnd = MSS
        self.in_slow_start = True
        self.bytes_acked_in_rtt = 0
        self.dup_ack_count = {}
        self.in_fast_recovery = False
        self.recover = self.base
    
    def on_fast_retransmit(self):
        """Handle fast retransmit (TCP Reno - 3 dup ACKs)"""
        print(f"Fast retransmit! cwnd: {self.cwnd/MSS:.1f} -> {self.cwnd/(2*MSS):.1f} MSS")
        self.ssthresh = max(self.cwnd // 2, 2 * MSS)
        self.cwnd = self.ssthresh + 3 * MSS  # Fast recovery
        self.in_slow_start = False
        self.bytes_acked_in_rtt = 0
        self.in_fast_recovery = True
        self.recover = self.next_seq
    
    def get_effective_window(self):
        """Get the effective send window (min of cwnd and in-flight limit)"""
        return int(self.cwnd)
    
    def send_file(self, client_addr, filename):
        """Send file using congestion control"""
        try:
            with open(filename, 'rb') as f:
                file_data = f.read()
        except FileNotFoundError:
            print(f"Error: File {filename} not found")
            return
        
        total_bytes = len(file_data)
        print(f"Starting file transfer: {total_bytes} bytes")
        
        self.sock.settimeout(0.001)
        self.time_start = time.time()
        
        # Reset state
        self.base = 0
        self.next_seq = 0
        self.packets = {}
        self.dup_ack_count = {}
        self.last_ack = 0
        self.cwnd = MSS
        self.ssthresh = min(INITIAL_SSTHRESH, max(4 * MSS, total_bytes))
        self.in_slow_start = True
        self.bytes_acked_in_rtt = 0
        self.cwnd_log = []
        self.in_fast_recovery = False
        self.recover = 0
        
        # Split file into chunks
        chunks = []
        for i in range(0, total_bytes, DATA_SIZE):
            chunks.append(file_data[i:i + DATA_SIZE])
        
        total_packets = len(chunks)
        print(f"Total packets to send: {total_packets}")
        
        last_progress_time = time.time()
        
        while self.base < total_bytes:
            # Get effective window size
            window_size = self.get_effective_window()
            
            # Send new packets within window
            while self.next_seq < total_bytes and (self.next_seq - self.base) < window_size:
                chunk_idx = self.next_seq // DATA_SIZE
                if chunk_idx < len(chunks):
                    data = chunks[chunk_idx]
                    packet = self.create_packet(self.next_seq, data)
                    self.sock.sendto(packet, client_addr)
                    self.packets[self.next_seq] = (packet, time.time())
                    self.next_seq += len(data)
            
            # Try to receive ACKs
            try:
                ack_packet, _ = self.sock.recvfrom(MAX_PAYLOAD)
                ack_num = self.parse_ack(ack_packet)
                
                if ack_num is not None and ack_num > self.base:
                    # New ACK
                    acked_bytes = ack_num - self.base
                    
                    # Update RTT
                    if self.base in self.packets:
                        _, send_time = self.packets[self.base]
                        sample_rtt = time.time() - send_time
                        self.update_rtt(sample_rtt)
                    
                    # Remove acknowledged packets
                    acked_seqs = [seq for seq in self.packets if seq < ack_num]
                    for seq in acked_seqs:
                        del self.packets[seq]
                    
                    self.base = ack_num
                    self.last_ack = ack_num
                    self.dup_ack_count = {}
                    
                    if self.in_fast_recovery and ack_num >= self.recover:
                        self.in_fast_recovery = False
                        self.cwnd = self.ssthresh

                    # Update congestion window
                    self.on_new_ack(acked_bytes)
                    
                    # Progress indicator
                    if time.time() - last_progress_time > 1.0:
                        progress = (self.base / total_bytes) * 100
                        print(f"Progress: {progress:.1f}% - cwnd: {self.cwnd/MSS:.1f} MSS, ssthresh: {self.ssthresh/MSS:.1f} MSS")
                        last_progress_time = time.time()
                
                elif ack_num is not None and ack_num == self.base:
                    # Duplicate ACK
                    self.dup_ack_count[ack_num] = self.dup_ack_count.get(ack_num, 0) + 1
                    
                    # Fast retransmit after 3 duplicate ACKs
                    if self.dup_ack_count[ack_num] == 3:
                        if self.base in self.packets:
                            packet, _ = self.packets[self.base]
                            self.sock.sendto(packet, client_addr)
                            self.packets[self.base] = (packet, time.time())
                            self.on_fast_retransmit()
                    
                    # Fast recovery: inflate window for additional dup ACKs
                    elif self.dup_ack_count[ack_num] > 3:
                        if self.in_fast_recovery:
                            self.cwnd += MSS
            
            except socket.timeout:
                pass
            
            # Check for timeouts
            current_time = time.time()
            for seq_num in sorted(self.packets.keys()):
                packet, send_time = self.packets[seq_num]
                if current_time - send_time > self.rto:
                    # Timeout - retransmit and handle congestion
                    self.sock.sendto(packet, client_addr)
                    self.packets[seq_num] = (packet, current_time)
                    self.on_timeout()
                    break
        
        # Send EOF marker
        eof_packet = self.create_packet(self.next_seq, b'EOF')
        for _ in range(5):
            self.sock.sendto(eof_packet, client_addr)
            time.sleep(0.05)
        
        duration = time.time() - self.time_start
        throughput = (total_bytes * 8 / duration / 1_000_000)
        print(f"\nFile transfer complete!")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Throughput: {throughput:.2f} Mbps")
        print(f"Final cwnd: {self.cwnd/MSS:.1f} MSS")
        
        # Save cwnd log for analysis
        # with open('cwnd_log.csv', 'w') as f:
        #     f.write("time,cwnd_mss\n")
        #     for t, cwnd in self.cwnd_log:
        #         f.write(f"{t:.3f},{cwnd:.2f}\n")
    
    def run(self):
        """Main server loop"""
        print("Waiting for client request...")
        
        while True:
            try:
                data, client_addr = self.sock.recvfrom(MAX_PAYLOAD)
                if len(data) > 0:
                    print(f"Received request from {client_addr}")
                    self.send_file(client_addr, 'data.txt')
                    break
            except KeyboardInterrupt:
                print("\nServer shutting down")
                break
        
        self.sock.close()

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 p2_server.py <SERVER_IP> <SERVER_PORT>")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    
    server = CongestionControlServer(server_ip, server_port)
    server.run()

if __name__ == "__main__":
    main()
