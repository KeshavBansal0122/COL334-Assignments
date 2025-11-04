#!/usr/bin/env python3
"""
Part 1 Client: Reliable UDP File Transfer
Receives file with sliding window protocol and sends ACKs
"""

import socket
import sys
import time
import struct
import logging
import os

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
        
        # Setup logging
        self.setup_logging()
        
        self.logger.info(f"Client connecting to {self.server_ip}:{self.server_port}")
        print(f"Client connecting to {self.server_ip}:{self.server_port}")
    
    def setup_logging(self):
        """Setup file-based logging"""
        log_file = 'client.log'
        # Clear previous log file if it exists
        if os.path.exists(log_file):
            open(log_file, 'w').close()
        
        self.logger = logging.getLogger('ReliableUDPClient')
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
    
    def parse_packet(self, packet):
        """Parse packet to extract chunk index and payload"""
        if len(packet) < HEADER_SIZE:
            return None, None
        
        chunk_idx = struct.unpack('!I', packet[:4])[0]
        data = packet[HEADER_SIZE:]
        return chunk_idx, data
    
    def create_ack(self, ack_num):
        """Create selective ACK packet for a specific chunk index"""
        # ACK packet: 4 bytes chunk index + 16 bytes reserved (no data)
        return struct.pack('!I', ack_num) + b'\x00' * 16
    
    def send_request(self):
        """Send file request to server with retries"""
        request = b'G'  # Single byte request
        
        for attempt in range(MAX_RETRIES):
            try:
                print(f"Sending request (attempt {attempt + 1}/{MAX_RETRIES})...")
                self.logger.debug(f"SEND: Request (attempt {attempt + 1}/{MAX_RETRIES})")
                self.sock.sendto(request, (self.server_ip, self.server_port))
                
                # Wait for first data packet
                self.sock.settimeout(REQUEST_TIMEOUT)
                data, _ = self.sock.recvfrom(MAX_PAYLOAD)
                self.logger.debug(f"RECV: First packet size={len(data)} bytes")
                
                if len(data) >= HEADER_SIZE:
                    print("Connection established!")
                    self.logger.info("Connection established!")
                    return data  # Return first packet
                    
            except socket.timeout:
                print(f"Timeout on attempt {attempt + 1}")
                self.logger.warning(f"TIMEOUT on request attempt {attempt + 1}")
                continue
        
        print("Failed to connect after maximum retries")
        self.logger.error("Failed to connect after maximum retries")
        return None
    
    def receive_file(self, output_filename):
        """Receive file and write to output_filename"""
        print(f"Receiving file to {output_filename}...")
        self.logger.info(f"Starting file reception to {output_filename}")
        
        # Send request and get first packet
        first_packet = self.send_request()
        if first_packet is None:
            return False
        
        # Set socket to non-blocking for receiving
        self.sock.settimeout(0.5)
        
        start_time = time.time()
        expected_chunk = 0
        pending_chunks = {}
        ordered_data = []
        highest_contiguous = -1

        # Process first packet
        packets_to_process = [first_packet]
        last_ack_time = time.time()
        consecutive_timeouts = 0

        while True:
            # Process any pending packets
            for packet in packets_to_process:
                chunk_idx, data = self.parse_packet(packet)

                if chunk_idx is None:
                    continue

                # Check for EOF
                if data == b'EOF':
                    print("Received EOF marker")
                    self.logger.info(f"RECV: EOF marker at seq={chunk_idx}")
                    final_ack = self.create_ack(chunk_idx)
                    for _ in range(5):
                        self.sock.sendto(final_ack, (self.server_ip, self.server_port))
                        self.logger.debug(f"SEND: ACK seq={chunk_idx} (for EOF)")

                    # Flush any final in-order chunks before writing
                    while expected_chunk in pending_chunks:
                        ordered_data.append(pending_chunks.pop(expected_chunk))
                        highest_contiguous = expected_chunk
                        expected_chunk += 1

                    try:
                        with open(output_filename, 'wb') as f:
                            f.write(b''.join(ordered_data))

                        duration = time.time() - start_time
                        total_bytes = sum(len(d) for d in ordered_data)
                        print(f"File received successfully: {total_bytes} bytes in {duration:.2f}s")
                        print(f"Throughput: {(total_bytes * 8 / duration / 1_000_000):.2f} Mbps")
                        self.logger.info(f"File received successfully: {total_bytes} bytes in {duration:.2f}s")
                        self.logger.info(f"Throughput: {(total_bytes * 8 / duration / 1_000_000):.2f} Mbps")
                        return True
                    except Exception as e:
                        print(f"Error writing file: {e}")
                        self.logger.error(f"Error writing file: {e}")
                        return False

                # Handle data chunk
                if chunk_idx < expected_chunk:
                    # Send cumulative ACK for duplicate packet
                    ack = self.create_ack(expected_chunk)
                    self.sock.sendto(ack, (self.server_ip, self.server_port))
                    self.logger.debug(f"RECV: Duplicate data seq={chunk_idx}, SEND: ACK seq={expected_chunk}")
                    last_ack_time = time.time()
                    continue

                if chunk_idx not in pending_chunks:
                    pending_chunks[chunk_idx] = data
                    if data:
                        self.logger.debug(f"RECV: Data seq={chunk_idx} size={len(data)} bytes")
                    else:
                        self.logger.debug(f"RECV: Data seq={chunk_idx} (empty)")

                # Deliver any newly in-order data to the output buffer
                while expected_chunk in pending_chunks:
                    ordered_data.append(pending_chunks.pop(expected_chunk))
                    highest_contiguous = expected_chunk
                    expected_chunk += DATA_SIZE
                
                # Send cumulative ACK with next expected sequence number
                ack = self.create_ack(expected_chunk)
                self.sock.sendto(ack, (self.server_ip, self.server_port))
                self.logger.debug(f"SEND: ACK seq={expected_chunk} (next expected)")
                last_ack_time = time.time()

            packets_to_process = []

            # Try to receive more packets
            try:
                packet, _ = self.sock.recvfrom(MAX_PAYLOAD)
                packets_to_process.append(packet)
                consecutive_timeouts = 0
            except socket.timeout:
                consecutive_timeouts += 1
                self.logger.debug(f"TIMEOUT: consecutive_timeouts={consecutive_timeouts}")

                # Re-acknowledge the next expected sequence to prompt retransmission
                if time.time() - last_ack_time > 0.2:
                    ack = self.create_ack(expected_chunk)
                    self.sock.sendto(ack, (self.server_ip, self.server_port))
                    self.logger.debug(f"SEND: Duplicate ACK seq={expected_chunk} (timeout)")
                    last_ack_time = time.time()

                # If too many consecutive timeouts, assume transfer is done
                if consecutive_timeouts > 20:
                    print("Transfer appears to be complete (timeout)")
                    self.logger.info("Transfer appears to be complete (timeout)")
                    break

        return False
    
    def run(self):
        """Main client loop"""
        success = self.receive_file('received_data.txt')
        self.sock.close()
        
        if success:
            print("Client finished successfully")
            self.logger.info("Client finished successfully")
        else:
            print("Client finished with errors")
            self.logger.error("Client finished with errors")

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
