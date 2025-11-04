#!/usr/bin/env python3
"""
Part 1 Server: Reliable UDP File Transfer with BBR Congestion Control
Implements BBR-inspired congestion control with sliding window protocol
"""

import socket
import sys
import time
import struct
import os
from collections import deque

# Constants
MAX_PAYLOAD = 1200
HEADER_SIZE = 20
DATA_SIZE = MAX_PAYLOAD - HEADER_SIZE  # 1180 bytes (MSS)
MSS = DATA_SIZE
INITIAL_TIMEOUT = 1.0

# BBR Constants
BBR_UNIT = 256  # Scaling factor (using 8-bit scale like BBR)
BBR_HIGH_GAIN = int(BBR_UNIT * 2.89)  # 2/ln(2) for startup
BBR_DRAIN_GAIN = int(BBR_UNIT * 1000 / 2885)  # Inverse of high_gain
BBR_CWND_GAIN = BBR_UNIT * 2
BBR_PROBE_RTT_DURATION = 0.2  # 200ms
BBR_MIN_RTT_WINDOW = 10.0  # 10 seconds
BBR_BW_WINDOW_ROUNDS = 10  # Track max bw over 10 rounds
BBR_FULL_BW_THRESH = int(BBR_UNIT * 1.25)  # 25% growth threshold
BBR_FULL_BW_COUNT = 3  # Rounds without growth to declare pipe full
BBR_MIN_CWND = 4  # Minimum cwnd in packets

# BBR Pacing gain cycle for PROBE_BW
BBR_PACING_GAIN_CYCLE = [
    int(BBR_UNIT * 1.25),  # Probe for more bw
    int(BBR_UNIT * 0.75),  # Drain queue
    BBR_UNIT, BBR_UNIT, BBR_UNIT,  # Cruise
    BBR_UNIT, BBR_UNIT, BBR_UNIT
]

class BBRMode:
    STARTUP = 0
    DRAIN = 1
    PROBE_BW = 2
    PROBE_RTT = 3

class BBRState:
    """BBR congestion control state"""
    def __init__(self):
        # RTT tracking
        self.min_rtt_us = float('inf')
        self.min_rtt_stamp = time.time()
        
        # Bandwidth tracking
        self.bw_samples = deque(maxlen=BBR_BW_WINDOW_ROUNDS)
        self.max_bw = 0
        
        # Round tracking
        self.round_count = 0
        self.round_start = False
        self.next_round_delivered = 0
        
        # Mode and gains
        self.mode = BBRMode.STARTUP
        self.pacing_gain = BBR_HIGH_GAIN
        self.cwnd_gain = BBR_HIGH_GAIN
        
        # Full pipe detection
        self.full_bw = 0
        self.full_bw_count = 0
        self.full_bw_reached = False
        
        # PROBE_BW cycle
        self.cycle_index = 0
        self.cycle_stamp = time.time()
        
        # PROBE_RTT
        self.probe_rtt_done_stamp = 0
        self.probe_rtt_round_done = False
        
        # Delivery tracking
        self.delivered = 0
        self.delivered_time = time.time()
        
        # Pacing
        self.pacing_rate = 0

class ReliableUDPServer:
    def __init__(self, server_ip, server_port, sws):
        self.server_ip = server_ip
        self.server_port = server_port
        self.sws = sws  # Sender Window Size in bytes (not used directly in BBR)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.server_ip, self.server_port))
        
        # BBR state
        self.bbr = BBRState()
        
        # Congestion window (in packets, starts at 1 MSS)
        self.cwnd = 1
        
        # RTT estimation (for timeout)
        self.estimated_rtt = INITIAL_TIMEOUT
        self.dev_rtt = 0
        self.rto = INITIAL_TIMEOUT
        
        # Window management
        self.base = 0  # First unacknowledged byte
        self.next_seq = 0  # Next byte to send
        self.packets = {}  # seq_num -> (data, send_time, size)
        self.dup_ack_count = {}  # ack_num -> count
        
        # Delivery rate tracking
        self.delivery_rate_samples = []
        
        print(f"Server listening on {self.server_ip}:{self.server_port}")
        print(f"BBR Congestion Control enabled, initial cwnd: {self.cwnd} packets ({self.cwnd * MSS} bytes)")
    
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
        """Update RTT estimates (for RTO calculation)"""
        ALPHA = 0.3
        BETA = 0.4
        self.estimated_rtt = (1 - ALPHA) * self.estimated_rtt + ALPHA * sample_rtt
        self.dev_rtt = (1 - BETA) * self.dev_rtt + BETA * abs(sample_rtt - self.estimated_rtt)
        self.rto = self.estimated_rtt + self.dev_rtt
        self.rto = max(0.1, min(self.rto, 2.0))
        
        # Update BBR min_rtt
        sample_rtt_us = sample_rtt * 1_000_000
        if sample_rtt_us < self.bbr.min_rtt_us:
            self.bbr.min_rtt_us = sample_rtt_us
            self.bbr.min_rtt_stamp = time.time()
    
    def update_bw(self, delivered, elapsed_us):
        """Update bandwidth estimate"""
        if elapsed_us <= 0 or delivered <= 0:
            return 0
        
        # Calculate delivery rate in bytes per second
        bw = (delivered * 1_000_000) / elapsed_us
        
        # Update max bandwidth filter (only if we have samples)
        if len(self.bbr.bw_samples) > 0:
            self.bbr.bw_samples.append(bw)
            self.bbr.max_bw = max(self.bbr.bw_samples)
        else:
            self.bbr.bw_samples.append(bw)
            self.bbr.max_bw = bw
        
        return bw
    
    def check_full_bw_reached(self):
        """Check if pipe is full during STARTUP"""
        if self.bbr.full_bw_reached or not self.bbr.round_start:
            return
        
        # Check if bandwidth has grown by at least 25%
        bw_thresh = (self.bbr.full_bw * BBR_FULL_BW_THRESH) // BBR_UNIT
        
        if self.bbr.max_bw >= bw_thresh:
            self.bbr.full_bw = self.bbr.max_bw
            self.bbr.full_bw_count = 0
        else:
            self.bbr.full_bw_count += 1
            if self.bbr.full_bw_count >= BBR_FULL_BW_COUNT:
                self.bbr.full_bw_reached = True
                print(f"BBR: Pipe full detected, max_bw: {self.bbr.max_bw / 1_000_000:.2f} Mbps")
    
    def update_mode(self):
        """Update BBR mode based on state"""
        if self.bbr.mode == BBRMode.STARTUP and self.bbr.full_bw_reached:
            self.bbr.mode = BBRMode.DRAIN
            print(f"BBR: Entering DRAIN mode, cwnd: {self.cwnd}")
        
        elif self.bbr.mode == BBRMode.DRAIN:
            # Check if queue is drained (inflight <= BDP)
            inflight_packets = len(self.packets)
            bdp_packets = self.calculate_bdp() // MSS
            if inflight_packets <= bdp_packets:
                self.bbr.mode = BBRMode.PROBE_BW
                self.bbr.cycle_index = 0
                self.bbr.cycle_stamp = time.time()
                print(f"BBR: Entering PROBE_BW mode")
        
        elif self.bbr.mode == BBRMode.PROBE_BW:
            # Check if we should enter PROBE_RTT
            if time.time() - self.bbr.min_rtt_stamp > BBR_MIN_RTT_WINDOW:
                self.bbr.mode = BBRMode.PROBE_RTT
                self.bbr.probe_rtt_done_stamp = 0
                self.bbr.probe_rtt_round_done = False
                print(f"BBR: Entering PROBE_RTT mode")
        
        elif self.bbr.mode == BBRMode.PROBE_RTT:
            # Exit PROBE_RTT after duration
            if self.bbr.probe_rtt_done_stamp > 0:
                if time.time() >= self.bbr.probe_rtt_done_stamp:
                    self.bbr.min_rtt_stamp = time.time()
                    self.bbr.mode = BBRMode.PROBE_BW if self.bbr.full_bw_reached else BBRMode.STARTUP
                    print(f"BBR: Exiting PROBE_RTT mode")
    
    def update_gains(self):
        """Update pacing and cwnd gains based on mode"""
        if self.bbr.mode == BBRMode.STARTUP:
            self.bbr.pacing_gain = BBR_HIGH_GAIN
            self.bbr.cwnd_gain = BBR_HIGH_GAIN
        
        elif self.bbr.mode == BBRMode.DRAIN:
            self.bbr.pacing_gain = BBR_DRAIN_GAIN
            self.bbr.cwnd_gain = BBR_HIGH_GAIN
        
        elif self.bbr.mode == BBRMode.PROBE_BW:
            self.bbr.pacing_gain = BBR_PACING_GAIN_CYCLE[self.bbr.cycle_index]
            self.bbr.cwnd_gain = BBR_CWND_GAIN
            
            # Advance cycle if appropriate
            if self.bbr.round_start:
                self.bbr.cycle_index = (self.bbr.cycle_index + 1) % len(BBR_PACING_GAIN_CYCLE)
        
        elif self.bbr.mode == BBRMode.PROBE_RTT:
            self.bbr.pacing_gain = BBR_UNIT
            self.bbr.cwnd_gain = BBR_UNIT
    
    def calculate_bdp(self):
        """Calculate bandwidth-delay product in bytes"""
        if self.bbr.min_rtt_us == float('inf') or self.bbr.max_bw == 0:
            return BBR_MIN_CWND * MSS
        
        # BDP = bw (bytes/sec) * rtt (seconds) = bytes
        min_rtt_sec = self.bbr.min_rtt_us / 1_000_000
        bdp = self.bbr.max_bw * min_rtt_sec
        return max(int(bdp), BBR_MIN_CWND * MSS)
    
    def update_cwnd(self):
        """Update congestion window based on BBR"""
        if self.bbr.mode == BBRMode.PROBE_RTT:
            # Cap at minimum
            self.cwnd = BBR_MIN_CWND
        else:
            # Calculate target cwnd
            bdp_bytes = self.calculate_bdp()
            target_cwnd_bytes = (bdp_bytes * self.bbr.cwnd_gain) // BBR_UNIT
            target_cwnd_packets = max(target_cwnd_bytes // MSS, BBR_MIN_CWND)
            
            # Move towards target
            if self.bbr.full_bw_reached:
                self.cwnd = target_cwnd_packets
            else:
                # In STARTUP, grow more aggressively
                self.cwnd = max(self.cwnd, target_cwnd_packets)
        
        self.cwnd = max(self.cwnd, BBR_MIN_CWND)
    
    def send_file(self, client_addr, filename):
        """Send file using BBR congestion control"""
        try:
            with open(filename, 'rb') as f:
                file_data = f.read()
        except FileNotFoundError:
            print(f"Error: File {filename} not found")
            return
        
        total_bytes = len(file_data)
        print(f"Starting file transfer: {total_bytes} bytes")
        
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
        last_print = start_time
        
        # Delivery tracking for bandwidth measurement
        last_delivered_bytes = 0
        last_delivered_time = start_time
        sample_start_time = start_time
        sample_start_seq = 0
        
        while self.base < total_bytes:
            current_time = time.time()
            
            # Send new packets within cwnd
            cwnd_bytes = self.cwnd * MSS
            while self.next_seq < total_bytes and (self.next_seq - self.base) < cwnd_bytes:
                chunk_idx = self.next_seq // DATA_SIZE
                if chunk_idx < len(chunks):
                    data = chunks[chunk_idx]
                    packet = self.create_packet(self.next_seq, data)
                    self.sock.sendto(packet, client_addr)
                    self.packets[self.next_seq] = (packet, current_time, len(data))
                    self.next_seq += len(data)
            
            # Try to receive ACKs
            try:
                ack_packet, _ = self.sock.recvfrom(MAX_PAYLOAD)
                ack_num = self.parse_ack(ack_packet)
                
                if ack_num is not None and ack_num > self.base:
                    # Calculate delivered bytes for this ACK
                    delivered_bytes = ack_num - self.base
                    
                    # Update RTT if we have timing info for the base packet
                    if self.base in self.packets:
                        _, send_time, _ = self.packets[self.base]
                        sample_rtt = current_time - send_time
                        self.update_rtt(sample_rtt)
                    
                    # Update bandwidth estimate using time since last sample
                    elapsed_us = (current_time - sample_start_time) * 1_000_000
                    total_delivered = ack_num - sample_start_seq
                    
                    if elapsed_us > 1000 and total_delivered > 0:  # At least 1ms elapsed
                        bw = self.update_bw(total_delivered, elapsed_us)
                        # Start new sample
                        sample_start_time = current_time
                        sample_start_seq = ack_num
                    
                    # Check for round completion
                    if ack_num >= self.bbr.next_round_delivered:
                        self.bbr.round_start = True
                        self.bbr.round_count += 1
                        self.bbr.next_round_delivered = self.next_seq
                        
                        self.check_full_bw_reached()
                    else:
                        self.bbr.round_start = False
                    
                    # Update BBR mode and gains
                    self.update_mode()
                    self.update_gains()
                    self.update_cwnd()
                    
                    # Remove acknowledged packets
                    acked_seqs = [seq for seq in self.packets if seq < ack_num]
                    for seq in acked_seqs:
                        del self.packets[seq]
                    
                    self.base = ack_num
                    self.dup_ack_count = {}
                    
                    last_delivered_bytes = ack_num
                    last_delivered_time = current_time
                    
                elif ack_num is not None and ack_num == self.base:
                    # Duplicate ACK - fast retransmit
                    self.dup_ack_count[ack_num] = self.dup_ack_count.get(ack_num, 0) + 1
                    
                    if self.dup_ack_count[ack_num] == 3:
                        if self.base in self.packets:
                            packet, _, _ = self.packets[self.base]
                            self.sock.sendto(packet, client_addr)
                            self.packets[self.base] = (packet, current_time, len(packet) - HEADER_SIZE)
                            print(f"Fast retransmit: seq {self.base}")
            
            except socket.timeout:
                pass
            
            # Check for timeouts
            current_time = time.time()
            for seq_num in list(self.packets.keys()):
                packet, send_time, size = self.packets[seq_num]
                if current_time - send_time > self.rto:
                    self.sock.sendto(packet, client_addr)
                    self.packets[seq_num] = (packet, current_time, size)
                    print(f"Timeout retransmit: seq {seq_num}, RTO: {self.rto:.3f}s")
                    break
            
            # Periodic status update
            if current_time - last_print > 1.0:
                progress = (self.base / total_bytes) * 100
                print(f"Progress: {progress:.1f}%, cwnd: {self.cwnd} pkts ({self.cwnd * MSS} bytes), "
                      f"mode: {['STARTUP', 'DRAIN', 'PROBE_BW', 'PROBE_RTT'][self.bbr.mode]}, "
                      f"bw: {self.bbr.max_bw / 1_000_000:.2f} Mbps, "
                      f"min_rtt: {self.bbr.min_rtt_us / 1000:.2f} ms")
                last_print = current_time
        
        # Send EOF marker
        eof_packet = self.create_packet(self.next_seq, b'EOF')
        for _ in range(5):
            self.sock.sendto(eof_packet, client_addr)
            time.sleep(0.1)
        
        duration = time.time() - start_time
        print(f"\nFile transfer complete in {duration:.2f} seconds")
        print(f"Throughput: {(total_bytes * 8 / duration / 1_000_000):.2f} Mbps")
        print(f"Final cwnd: {self.cwnd} packets ({self.cwnd * MSS} bytes)")
        print(f"BBR max_bw: {self.bbr.max_bw / 1_000_000:.2f} Mbps")
        print(f"BBR min_rtt: {self.bbr.min_rtt_us / 1000:.2f} ms")
    
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