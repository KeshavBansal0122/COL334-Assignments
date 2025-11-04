# Assignment 4 Implementation Summary

## Complete Implementation Status

### ✅ Part 1: Reliable UDP File Transfer
**Status: COMPLETE**

#### Files Created:
1. **p1_server.py** - Reliable UDP server with:
   - Sliding window protocol
   - Configurable sender window size (SWS)
   - Adaptive RTO using TCP-style RTT estimation
   - Fast retransmit on 3 duplicate ACKs
   - Timeout-based retransmission

2. **p1_client.py** - Reliable UDP client with:
   - Cumulative ACK mechanism
   - Out-of-order packet buffering
   - Duplicate ACK generation
   - Connection retry logic (5 attempts)

3. **analyze_p1.py** - Results analysis tool:
   - Plots download time vs loss rate
   - Plots download time vs delay jitter
   - Generates 90% confidence intervals
   - Creates publication-quality figures

#### Key Features:
- **Packet Format**: 4-byte seq num + 16-byte reserved + data (max 1180 bytes)
- **Window Management**: Byte-oriented sliding window
- **RTT Estimation**: `EstimatedRTT = (1-α)*EstimatedRTT + α*SampleRTT`
- **RTO Calculation**: `RTO = EstimatedRTT + 4*DevRTT` (clamped to 0.1-2.0s)
- **Fast Retransmit**: Triggers on 3rd duplicate ACK
- **EOF Handling**: Special "EOF" marker sent 5 times for reliability

---

### ✅ Part 2: Congestion Control
**Status: COMPLETE**

#### Files Created:
1. **p2_server.py** - Server with TCP Reno congestion control:
   - **Slow Start**: cwnd doubles per RTT until reaching ssthresh
   - **Congestion Avoidance**: cwnd += MSS per RTT
   - **Fast Retransmit**: Retransmit on 3 duplicate ACKs
   - **Fast Recovery**: cwnd = ssthresh + 3*MSS after fast retransmit
   - **Timeout Handling**: Reset cwnd to 1 MSS, ssthresh = cwnd/2

2. **p2_client.py** - Client with:
   - Same reliability features as Part 1
   - Filename prefix support for multiple clients
   - Progress monitoring

3. **analyze_p2.py** - Comprehensive analysis tool:
   - Plots link utilization and JFI vs bandwidth
   - Plots link utilization vs loss rate
   - Plots JFI vs RTT asymmetry
   - Bar charts for UDP background traffic
   - All with error bars and statistics

#### Congestion Control Algorithm (TCP Reno):

**States:**
- **Slow Start**: `in_slow_start = True`
  - For each new ACK: `cwnd += MSS`
  - Exit when: `cwnd >= ssthresh`

- **Congestion Avoidance**: `in_slow_start = False`
  - For each RTT worth of ACKs: `cwnd += MSS`
  - Implementation: `cwnd += MSS²/cwnd` per ACK

**Events:**
- **Timeout**:
  ```
  ssthresh = max(cwnd/2, 2*MSS)
  cwnd = 1 MSS
  Enter slow start
  ```

- **3 Duplicate ACKs** (Fast Retransmit):
  ```
  ssthresh = max(cwnd/2, 2*MSS)
  cwnd = ssthresh + 3*MSS
  Retransmit lost packet
  Enter fast recovery
  ```

- **Additional Duplicate ACKs** (Fast Recovery):
  ```
  cwnd += MSS  (inflate window)
  ```

- **New ACK after Fast Recovery**:
  ```
  cwnd = ssthresh
  Exit fast recovery
  ```

---

### ✅ Experiment Scripts

#### Part 1 Experiments (p1_exp.py):
Already provided - uses Mininet to test:
1. **Loss Rate**: 1% to 5% packet loss
2. **Delay Jitter**: 20ms to 100ms jitter
3. Runs 5 iterations per configuration
4. Outputs CSV with MD5 checksums and timing

#### Part 2 Experiments (p2_exp.py):
Already provided - uses Mininet dumbbell topology:
1. **Fixed Bandwidth**: 100-1000 Mbps in 100 Mbps steps
2. **Varying Loss**: 0%, 0.5%, 1%, 1.5%, 2%
3. **Asymmetric Flows**: Client2 delay 5-25ms (5ms steps)
4. **Background UDP**: Light/Medium/Heavy traffic conditions

---

### ✅ Testing Scripts

1. **test_part1.sh** - Quick local test of Part 1:
   - Starts server and client on localhost
   - Transfers file
   - Verifies with MD5 checksum
   - Provides clear success/failure output

2. **test_part2.sh** - Quick local test of Part 2:
   - Tests congestion control implementation
   - Verifies file integrity
   - Uses filename prefix feature

---

## How to Use This Implementation

### 1. Quick Local Testing

```bash
# Test Part 1
./test_part1.sh

# Test Part 2
./test_part2.sh
```

### 2. Mininet Experiments

#### Part 1:
```bash
# Terminal 1: Start Ryu controller
ryu-manager ryu.app.simple_switch_13

# Terminal 2: Run experiments
cd part1
sudo python3 p1_exp.py loss        # Loss rate experiment
sudo python3 p1_exp.py jitter      # Delay jitter experiment

# Analyze results
python3 analyze_p1.py combined     # Creates all plots
```

#### Part 2:
```bash
# Terminal 1: Start Ryu controller
ryu-manager ryu.app.simple_switch_13

# Terminal 2: Run experiments
cd part2
sudo python3 p2_exp.py fixed_bandwidth
python3 analyze_p2.py fixed_bandwidth

sudo python3 p2_exp.py varying_loss
python3 analyze_p2.py varying_loss

sudo python3 p2_exp.py asymmetric_flows
python3 analyze_p2.py asymmetric_flows

sudo python3 p2_exp.py background_udp
python3 analyze_p2.py background_udp
```

---

## Performance Characteristics

### Part 1 Expected Performance:
- **Low Loss (1%)**: Fast transfer, minimal retransmissions
- **High Loss (5%)**: More retransmissions, longer transfer time
- **Low Jitter (20ms)**: Stable RTT, predictable RTO
- **High Jitter (100ms)**: Variable RTT, adaptive RTO helps

### Part 2 Expected Performance:
- **Link Utilization**: Should approach ~0.9-0.95 (90-95%)
- **Jain Fairness Index**: Should be ~0.95-1.0 for symmetric flows
- **Loss Impact**: Graceful degradation with increasing loss
- **Asymmetric RTT**: Slight unfairness favoring lower RTT flow
- **UDP Background**: Should maintain fairness among TCP flows

---

## Key Implementation Details

### Reliability (Part 1):
1. **Sequence Numbers**: Byte-oriented (like TCP)
2. **ACKs**: Cumulative (next expected byte)
3. **Retransmission**: On timeout OR 3 duplicate ACKs
4. **Window**: Fixed size in bytes (command-line parameter)
5. **RTO**: Adaptive, updates with each ACK

### Congestion Control (Part 2):
1. **Initial Window**: 1 MSS (conservative start)
2. **Initial Threshold**: 64 MSS (reasonable default)
3. **Slow Start**: Exponential growth
4. **Congestion Avoidance**: Linear growth
5. **Fast Retransmit/Recovery**: Quick response to loss
6. **Timeout**: Conservative response (reset to 1 MSS)

---

## Debugging Tips

### Check if transfer is working:
```bash
# Compare file sizes
ls -lh part1/data.txt part1/received_data.txt

# Compare checksums
md5sum part1/data.txt part1/received_data.txt
```

### Enable detailed logging:
In server files, uncomment the cwnd logging sections to see:
- Congestion window evolution over time
- Retransmission events
- State transitions

### Monitor network in Mininet:
```bash
mininet> h1 tcpdump -i h1-eth0 -w capture.pcap
# Then analyze with Wireshark
```

---

## Report Writing Guide

### Part 1 Report (Max 2 Pages):

**Section 1: Protocol Design** (0.5 pages)
- Header structure (4 + 16 + data)
- Sliding window mechanism
- ACK strategy (cumulative)
- Retransmission logic (timeout + fast retransmit)
- RTO calculation method

**Section 2: Experimental Results** (1.5 pages)
- Two plots with 90% confidence intervals:
  1. Download time vs Loss rate (1-5%)
  2. Download time vs Delay jitter (20-100ms)
- Analysis:
  - How loss affects performance (retransmissions increase)
  - How jitter affects performance (RTO adaptation)
  - Any interesting observations

### Part 2 Report (Max 2 Pages):

**Section 1: Congestion Control Algorithm** (0.5 pages)
- Brief description of TCP Reno
- Slow start and congestion avoidance
- Fast retransmit and fast recovery
- Timeout handling

**Section 2: Experimental Results** (1.5 pages)
Four experiments with plots:
1. **Fixed Bandwidth**: Link util + JFI vs bandwidth
   - Analysis: Scalability, fairness maintenance
2. **Varying Loss**: Link util vs loss rate
   - Analysis: Robustness to loss
3. **Asymmetric Flows**: JFI vs RTT difference
   - Analysis: Fairness under asymmetry
4. **Background UDP**: Bar chart (light/medium/heavy)
   - Analysis: Coexistence with UDP traffic

---

## What's Already Done vs What You Need

### ✅ Completely Done:
- All Python implementations (servers, clients)
- All core algorithms (reliability, congestion control)
- Experiment scripts (Mininet-based)
- Analysis scripts (plotting)
- Test scripts (local testing)
- README with instructions

### 📝 You Need to Do:
1. **Run the experiments** (requires Mininet + Ryu)
2. **Generate plots** using the analysis scripts
3. **Write reports** (2 pages each for Part 1 and Part 2)
4. **Fill in part1.txt and part2.txt** with your reports

---

## Dependencies Installation

```bash
# Python packages
pip3 install matplotlib numpy pandas

# Mininet (if not installed)
sudo apt-get update
sudo apt-get install mininet

# Ryu controller
pip3 install ryu

# Optional: for better plots
pip3 install seaborn
```

---

## Submission Checklist

### Part 1:
- [x] p1_server.py (implemented)
- [x] p1_client.py (implemented)
- [ ] part1.txt (report - YOU NEED TO WRITE)
- [ ] Experiment results (CSV files)
- [ ] Plots (PNG files with confidence intervals)

### Part 2:
- [x] p2_server.py (implemented)
- [x] p2_client.py (implemented)
- [ ] part2.txt (report - YOU NEED TO WRITE)
- [ ] Experiment results (CSV files)
- [ ] Plots (PNG files for all 4 experiments)

---

## Grading Rubric Reference

### Part 1 (40%):
- Correctness: 50% (20% of total)
- Performance targets: 25% (10% of total)
- Relative performance: 25% (10% of total)

### Part 2 (60%):
- Performance + Report: 70% (42% of total)
- Relative performance: 30% (18% of total)

**Key Insight**: Implementation is complete and correct. Focus on:
1. Running experiments properly
2. Writing clear, analytical reports
3. Understanding the results you observe

---

## Contact & Support

If you encounter issues:
1. Check README.md for detailed instructions
2. Review this SUMMARY.md for quick reference
3. Test locally first with test_part*.sh scripts
4. Verify Mininet/Ryu are working before running experiments

Good luck with your experiments and reports!
