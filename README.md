# Assignment 4: Reliable UDP File Transfer with Congestion Control

This repository contains the complete implementation of a reliable file transfer protocol over UDP with congestion control mechanisms.

## Project Structure

```
.
├── part1/                      # Part 1: Reliability
│   ├── p1_server.py           # Server with sliding window protocol
│   ├── p1_client.py           # Client with ACKs and retransmission
│   ├── p1_exp.py              # Mininet experiment script
│   ├── data.txt               # File to transfer
│   └── part1.txt              # Report (to be created)
│
├── part2/                      # Part 2: Congestion Control
│   ├── p2_server.py           # Server with TCP Reno-like congestion control
│   ├── p2_client.py           # Client with ACKs
│   ├── p2_exp.py              # Mininet experiment script
│   ├── analyze_p2.py          # Results analysis and plotting
│   ├── udp_server.py          # Background UDP traffic server
│   ├── udp_client.py          # Background UDP traffic client
│   ├── data.txt               # File to transfer
│   └── part2.txt              # Report (to be created)
│
└── assignment4.md             # Assignment description
```

## Part 1: Reliability Implementation

### Features Implemented

1. **Sliding Window Protocol**
   - Sender window size (SWS) configurable via command line
   - Byte-oriented sequence numbering
   - In-order packet delivery

2. **Reliability Mechanisms**
   - Cumulative ACKs (TCP-style)
   - Timeout-based retransmission with adaptive RTO
   - Fast retransmit (3 duplicate ACKs)
   - Out-of-order packet buffering

3. **RTT Estimation**
   - Exponential weighted moving average (EWMA)
   - TCP-like RTO calculation: `RTO = EstimatedRTT + 4 * DevRTT`

### Running Part 1

#### Basic Usage

```bash
# Terminal 1: Start server
cd part1
python3 p1_server.py 10.0.0.1 6555 5900

# Terminal 2: Start client
python3 p1_client.py 10.0.0.1 6555
```

#### Running Experiments in Mininet

```bash
# Start Ryu controller (Terminal 1)
ryu-manager ryu.app.simple_switch_13

# Run loss rate experiment (Terminal 2)
cd part1
sudo python3 p1_exp.py loss

# Run jitter experiment
sudo python3 p1_exp.py jitter
```

### Packet Format

```
+-----------------+-------------------+-------------------------+
| Seq Number      | Reserved          | Data                    |
| (4 bytes)       | (16 bytes)        | (up to 1180 bytes)      |
+-----------------+-------------------+-------------------------+
```

## Part 2: Congestion Control Implementation

### Features Implemented

1. **TCP Reno-like Congestion Control**
   - Slow start: exponential growth (cwnd doubles per RTT)
   - Congestion avoidance: additive increase (cwnd += MSS per RTT)
   - Fast retransmit: retransmit on 3 duplicate ACKs
   - Fast recovery: cwnd = ssthresh + 3*MSS

2. **Congestion Events Handling**
   - Timeout: ssthresh = cwnd/2, cwnd = 1 MSS, enter slow start
   - 3 dup ACKs: ssthresh = cwnd/2, cwnd = ssthresh + 3 MSS, enter fast recovery

3. **Dynamic Window Management**
   - Initial cwnd = 1 MSS (1180 bytes)
   - Initial ssthresh = 64 MSS
   - Window size adapts to network conditions

### Running Part 2

#### Basic Usage

```bash
# Terminal 1: Start server
cd part2
python3 p2_server.py 10.0.0.1 6555

# Terminal 2: Start client
python3 p2_client.py 10.0.0.1 6555 client1_
```

The client will save the file as `client1_received_data.txt`.

#### Running Experiments in Mininet

```bash
# Start Ryu controller (Terminal 1)
ryu-manager ryu.app.simple_switch_13

# Run experiments (Terminal 2)
cd part2

# Experiment 1: Fixed bandwidth
sudo python3 p2_exp.py fixed_bandwidth
python3 analyze_p2.py fixed_bandwidth

# Experiment 2: Varying loss
sudo python3 p2_exp.py varying_loss
python3 analyze_p2.py varying_loss

# Experiment 3: Asymmetric flows
sudo python3 p2_exp.py asymmetric_flows
python3 analyze_p2.py asymmetric_flows

# Experiment 4: Background UDP
sudo python3 p2_exp.py background_udp
python3 analyze_p2.py background_udp
```

### Experiments

1. **Fixed Bandwidth (100-1000 Mbps)**
   - Measures link utilization and fairness across different bandwidths
   - Tests scalability of congestion control

2. **Varying Loss (0-2%)**
   - Studies impact of packet loss on throughput
   - Tests robustness of retransmission mechanisms

3. **Asymmetric Flows**
   - Client2 delay varies from 5ms to 25ms
   - Measures fairness when RTTs differ between flows

4. **Background UDP Traffic**
   - Tests behavior with bursty cross-traffic
   - Three conditions: Light (1.5s), Medium (0.8s), Heavy (0.5s) OFF periods

## Dependencies

### Required Packages

```bash
# Python packages
pip3 install matplotlib numpy pandas

# Mininet
sudo apt-get install mininet

# Ryu controller
pip3 install ryu
```

## Key Design Decisions

### Part 1

1. **Fixed Window Size**: SWS is provided as a command-line parameter (not dynamic)
2. **Cumulative ACKs**: Simple and efficient, reduces ACK overhead
3. **Fast Retransmit**: Triggers on 3 duplicate ACKs to avoid timeout delays
4. **Adaptive RTO**: Uses TCP-style RTT estimation for dynamic timeout values

### Part 2

1. **TCP Reno Algorithm**: Well-studied, proven performance
2. **Conservative Initial Window**: Starts at 1 MSS to probe network capacity safely
3. **Byte-Oriented**: Congestion window tracks bytes, not packets
4. **Fast Recovery**: Maintains higher throughput after packet loss

## Performance Optimization Tips

1. **Buffer Sizing**: Use BDP (Bandwidth-Delay Product) = RTT × BW
2. **Initial ssthresh**: Set based on expected bandwidth
3. **RTO Bounds**: Clamped between 0.1s and 2.0s to avoid extremes
4. **MSS Selection**: 1180 bytes leaves room for 20-byte header

## Debugging

### Enable Verbose Logging

In server files, uncomment the cwnd logging:
```python
with open('cwnd_log.csv', 'w') as f:
    for t, cwnd in self.cwnd_log:
        f.write(f"{t:.3f},{cwnd:.2f}\n")
```

### Common Issues

1. **File transfer stuck**: Check if server/client are on the same network
2. **High retransmissions**: Increase RTO or check for network congestion
3. **Low throughput**: Verify cwnd is growing properly in slow start
4. **Fairness issues**: Check if flows have similar RTTs

## Testing

### Verify File Integrity

```bash
# Compare checksums
md5sum part1/data.txt
md5sum part1/received_data.txt
```

### Monitor Network

```bash
# In Mininet
mininet> h1 tcpdump -i h1-eth0 -w capture.pcap
```

## Report Guidelines

### Part 1 Report (max 2 pages)

1. Header structure and design choices
2. Reliability mechanisms implemented
3. Plots: Download time vs loss rate and delay jitter (with 90% confidence intervals)
4. Analysis of results

### Part 2 Report (max 2 pages)

1. Congestion control algorithm description
2. Four experiment plots with analysis:
   - Link utilization and JFI vs bandwidth
   - Link utilization vs loss rate
   - JFI vs RTT asymmetry
   - Bar chart for UDP background traffic
3. Discussion of observations

## References

- RFC 793: Transmission Control Protocol
- RFC 2018: TCP Selective Acknowledgment Options
- RFC 6298: Computing TCP's Retransmission Timer
- TCP Reno: Jacobson, V. "Congestion Avoidance and Control"

## Authors

Assignment 4 - COL334 Computer Networks

## License

Academic use only.
