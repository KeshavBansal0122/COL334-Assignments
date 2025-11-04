#!/usr/bin/env python3
"""
Part 1 Server: Reliable UDP File Transfer
Implements sliding window protocol with ACKs, timeouts, fast retransmit,
and CUBIC Congestion Control.
"""

import socket
import sys
import time
import struct
import os

# Constants
MAX_PAYLOAD = 1200
HEADER_SIZE = 20
DATA_SIZE = MAX_PAYLOAD - HEADER_SIZE  # 1180 bytes
INITIAL_TIMEOUT = 1.0
ALPHA = 1/8
BETA = 1/4
K = 4

class ReliableUDPServer:
    def __init__(self, server_ip, server_port, initial_cwnd=DATA_SIZE):
        self.server_ip = server_ip
        self.server_port = server_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.server_ip, self.server_port))
        
        # RTT estimation
        self.estimated_rtt = INITIAL_TIMEOUT
        self.dev_rtt = 0
        self.rto = INITIAL_TIMEOUT
        
        # Window management
        self.base = 0  # First unacknowledged byte
        self.next_seq = 0  # Next byte to send
        self.packets = {}  # seq_num -> (data, send_time)
        self.dup_ack_count = {}  # ack_num -> count
        
        # CUBIC Congestion Control
        self.initial_cwnd = initial_cwnd  # Initial window size in bytes
        self.cwnd = initial_cwnd
        self.ssthresh = 65535  # Start high
        self.w_max = 0
        self.t_epoch_start = 0
        self.min_rtt = float('inf')
        self.beta_cubic = 0.7  # Multiplicative decrease factor
        self.C = 0.4  # CUBIC constant
        self.last_congestion_event_time = 0
        
        print(f"Server listening on {self.server_ip}:{self.server_port}")
        print(f"Initial CWND: {self.initial_cwnd} bytes ({self.initial_cwnd / DATA_SIZE:.1f} MSS)")
    
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
        self.estimated_rtt = (1 - ALPHA) * self.estimated_rtt + ALPHA * sample_rtt
        self.dev_rtt = (1 - BETA) * self.dev_rtt + BETA * abs(sample_rtt - self.estimated_rtt)
        self.rto = self.estimated_rtt + K * self.dev_rtt
        self.rto = max(0.1, min(self.rto, 2.0))  # Clamp between 0.1 and 2 seconds
        
        # CUBIC needs the minimum RTT
        self.min_rtt = min(self.min_rtt, sample_rtt)

    def handle_congestion_event(self):
        """Handle a congestion event (timeout or fast retransmit)."""
        current_time = time.time()
        # Debounce: Only trigger one event per RTO
        if current_time - self.last_congestion_event_time < self.rto:
            return
        
        self.last_congestion_event_time = current_time
        self.t_epoch_start = current_time  # Start new CUBIC epoch
        self.w_max = self.cwnd  # Save max window
        
        # Multiplicative decrease
        self.ssthresh = max(self.cwnd * self.beta_cubic, 2 * DATA_SIZE)
        self.cwnd = self.ssthresh  # CUBIC fast recovery
        self.dup_ack_count = {}  # Reset dup ACKs
        
        print(f"--- Congestion Event --- W_max={self.w_max / DATA_SIZE:.1f}, "
              f"ssthresh={self.ssthresh / DATA_SIZE:.1f}, "
              f"new cwnd={self.cwnd / DATA_SIZE:.1f} MSS")

    def update_cwnd_on_ack(self):
        """Update CWND on receiving a new ACK, following CUBIC."""
        
        if self.cwnd < self.ssthresh:
            # Slow Start: Increase exponentially (one MSS per ACK)
            self.cwnd += DATA_SIZE
        else:
            # Congestion Avoidance (CUBIC)
            current_time = time.time()
            if self.t_epoch_start == 0:
                # First time in C.A. since last event
                self.t_epoch_start = current_time
                self.w_max = self.cwnd

            t = current_time - self.t_epoch_start
            rtt = self.min_rtt if self.min_rtt != float('inf') else self.estimated_rtt
            rtt = max(rtt, 0.001)  # Avoid division by zero
            
            # K = (W_max * (1-beta) / C)^(1/3)
            k_term = (self.w_max * (1.0 - self.beta_cubic)) / self.C
            k = k_term ** (1/3.0) if k_term >= 0 else 0
            
            # W_cubic(t + RTT)
            w_target_time = t + rtt
            w_cubic_target = self.C * ((w_target_time - k) ** 3) + self.w_max
            
            # TCP-friendly check (concave region)
            w_tcp = self.w_max * self.beta_cubic + (3 * (1 - self.beta_cubic) / (1 + self.beta_cubic)) * (t / rtt) * DATA_SIZE
            
            if w_cubic_target < w_tcp:
                w_target = w_tcp
            else:
                w_target = w_cubic_target
            
            # Increase cwnd towards the target
            if w_target > self.cwnd:
                # (w_target - cwnd) / cwnd * MSS
                increase = (w_target - self.cwnd) / self.cwnd * DATA_SIZE
                self.cwnd += increase
            else:
                # Standard Reno-like increase if at/above target
                self.cwnd += (DATA_SIZE * DATA_SIZE) / self.cwnd
        
        self.cwnd = max(self.cwnd, 2 * DATA_SIZE) # Ensure cwnd is at least 2*MSS

    def send_file(self, client_addr, filename):
        """Send file using sliding window protocol"""
        try:
            with open(filename, 'rb') as f:
                file_data = f.read()
        except FileNotFoundError:
            print(f"Error: File {filename} not found")
            return
        
        total_bytes = len(file_data)
        print(f"Starting file transfer: {total_bytes} bytes")
        
        # Set socket to non-blocking
        self.sock.settimeout(0.001)
        
        start_time = time.time()
        
        # Reset state for this transfer
        self.base = 0
        self.next_seq = 0
        self.packets = {}
        self.dup_ack_count = {}
        
        # Reset CUBIC state
        self.cwnd = self.initial_cwnd
        self.ssthresh = 65535
        self.w_max = 0
        self.t_epoch_start = 0
        self.min_rtt = float('inf')
        self.last_congestion_event_time = 0

        # Split file into chunks
        chunks = []
        for i in range(0, total_bytes, DATA_SIZE):
            chunks.append(file_data[i:i + DATA_SIZE])
        
        total_packets = len(chunks)
        print(f"Total packets to send: {total_packets}")
        
        while self.base < total_bytes:
            # Send new packets within window
            # Use dynamic self.cwnd instead of fixed self.sws
            while self.next_seq < total_bytes and (self.next_seq - self.base) < self.cwnd:
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
                    
                    # New ACK, update CWND
                    self.update_cwnd_on_ack()
                    
                elif ack_num is not None and ack_num == self.base:
                    # Duplicate ACK
                    self.dup_ack_count[ack_num] = self.dup_ack_count.get(ack_num, 0) + 1
                    
                    # Fast retransmit after 3 duplicate ACKs (count == 2)
                    if self.dup_ack_count[ack_num] == 3:
                        if self.base in self.packets:
                            print(f"Fast retransmit: seq {self.base}")
                            # Congestion event
                            self.handle_congestion_event()
                            
                            packet, _ = self.packets[self.base]
                            self.sock.sendto(packet, client_addr)
                            self.packets[self.base] = (packet, time.time())
            
            except socket.timeout:
                pass
            
            # Check for timeouts
            current_time = time.time()
            for seq_num in list(self.packets.keys()):
                packet, send_time = self.packets[seq_num]
                if current_time - send_time > self.rto:
                    # Timeout - retransmit
                    print(f"Timeout retransmit: seq {seq_num}, RTO: {self.rto:.3f}s")
                    
                    # Congestion event
                    self.handle_congestion_event()
                    
                    self.sock.sendto(packet, client_addr)
                    self.packets[seq_num] = (packet, current_time)
                    break  # Only retransmit one packet per timeout check
        
        # Send EOF marker
        eof_packet = self.create_packet(self.next_seq, b'EOF')
        for _ in range(5):  # Send EOF multiple times to ensure delivery
            self.sock.sendto(eof_packet, client_addr)
            time.sleep(0.1)
        
        duration = time.time() - start_time
        if duration > 0:
            print(f"File transfer complete in {duration:.2f} seconds")
            print(f"Throughput: {(total_bytes * 8 / duration / 1_000_000):.2f} Mbps")
        else:
            print("File transfer complete.")
    
    def run(self):
        """Main server loop"""
        print("Waiting for client request...")
        
        while True:
            try:
                # Set blocking timeout for initial request
                self.sock.settimeout(None)
                data, client_addr = self.sock.recvfrom(MAX_PAYLOAD)
                if len(data) > 0:
                    print(f"Received request from {client_addr}")
                    self.send_file(client_addr, 'data.txt')
                    print("\nWaiting for next client request...")
            
            except KeyboardInterrupt:
                print("\nServer shutting down")
                break
            except Exception as e:
                print(f"An error occurred: {e}")
                
        self.sock.close()

def main():
    if len(sys.argv) != 3:
        # Changed SWS to INITIAL_CWND
        print("Usage: python3 p1_server.py <SERVER_IP> <SERVER_PORT>")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    
    # Pass initial_cwnd instead of sws
    server = ReliableUDPServer(server_ip, server_port)
    server.run()

if __name__ == "__main__":
    main()