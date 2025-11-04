#!/usr/bin/env python3
"""
Part 2 Results Analysis and Visualization
Generates plots for all experiments
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys
import os

def plot_fixed_bandwidth(csv_file):
    """Plot link utilization and JFI vs bandwidth"""
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    df.columns = df.columns.str.strip()
    
    # Group by bandwidth and calculate mean and std
    grouped = df.groupby('bw').agg({
        'link_util': ['mean', 'std'],
        'jfi': ['mean', 'std']
    }).reset_index()

    # Flatten column names
    grouped.columns = ['bw', 'util_mean', 'util_std', 'jfi_mean', 'jfi_std']
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Plot link utilization
    ax1.errorbar(grouped['bw'], grouped['util_mean'], 
                 yerr=grouped['util_std'], 
                 marker='o', capsize=5, linewidth=2, markersize=8,
                 color='#2E86AB', label='Link Utilization')
    ax1.set_xlabel('Bottleneck Bandwidth (Mbps)', fontsize=12)
    ax1.set_ylabel('Link Utilization', fontsize=12)
    ax1.set_title('Link Utilization vs Bandwidth', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_ylim([0, 1.2])
    
    # Plot JFI
    ax2.errorbar(grouped['bw'], grouped['jfi_mean'], 
                 yerr=grouped['jfi_std'], 
                 marker='s', capsize=5, linewidth=2, markersize=8,
                 color='#A23B72', label='Jain Fairness Index')
    ax2.set_xlabel('Bottleneck Bandwidth (Mbps)', fontsize=12)
    ax2.set_ylabel('Jain Fairness Index', fontsize=12)
    ax2.set_title('Fairness vs Bandwidth', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    ax2.set_ylim([0, 1.1])
    
    plt.tight_layout()
    plt.savefig('p2_fixed_bandwidth.png', dpi=300, bbox_inches='tight')
    print("Saved: p2_fixed_bandwidth.png")
    
    # Print statistics
    print("\n=== Fixed Bandwidth Results ===")
    for _, row in grouped.iterrows():
        bw = row['bw']
        util_mean = row['util_mean']
        util_std = row['util_std']
        jfi_mean = row['jfi_mean']
        jfi_std = row['jfi_std']
        print(f"BW {bw:4.0f} Mbps: Util = {util_mean:.3f} ± {util_std:.3f}, JFI = {jfi_mean:.3f} ± {jfi_std:.3f}")

def plot_varying_loss(csv_file):
    """Plot link utilization vs loss rate"""
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    df.columns = df.columns.str.strip()
    
    grouped = df.groupby('loss').agg({
        'link_util': ['mean', 'std']
    }).reset_index()

    # Flatten column names
    grouped.columns = ['loss', 'util_mean', 'util_std']
    
    plt.figure(figsize=(10, 6))
    plt.errorbar(grouped['loss'], grouped['util_mean'], 
                 yerr=grouped['util_std'], 
                 marker='o', capsize=5, linewidth=2, markersize=8,
                 color='#E63946')
    plt.xlabel('Packet Loss Rate (%)', fontsize=12)
    plt.ylabel('Link Utilization', fontsize=12)
    plt.title('Impact of Packet Loss on Link Utilization', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.ylim([0, 1.2])
    
    plt.tight_layout()
    plt.savefig('p2_varying_loss.png', dpi=300, bbox_inches='tight')
    print("Saved: p2_varying_loss.png")
    
    print("\n=== Varying Loss Results ===")
    for _, row in grouped.iterrows():
        loss = row['loss']
        util_mean = row['util_mean']
        util_std = row['util_std']
        print(f"Loss {loss:.1f}%: Util = {util_mean:.3f} ± {util_std:.3f}")

def plot_asymmetric_flows(csv_file):
    """Plot JFI vs RTT difference"""
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    df.columns = df.columns.str.strip()
    
    grouped = df.groupby('delay_c2_ms').agg({
        'jfi': ['mean', 'std']
    }).reset_index()

    # Flatten column names
    grouped.columns = ['delay_c2_ms', 'jfi_mean', 'jfi_std']
    
    plt.figure(figsize=(10, 6))
    plt.errorbar(grouped['delay_c2_ms'], grouped['jfi_mean'], 
                 yerr=grouped['jfi_std'], 
                 marker='s', capsize=5, linewidth=2, markersize=8,
                 color='#06A77D')
    plt.xlabel('Client2-Switch Delay (ms)', fontsize=12)
    plt.ylabel('Jain Fairness Index', fontsize=12)
    plt.title('Impact of Asymmetric RTTs on Fairness', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.ylim([0, 1.1])
    
    plt.tight_layout()
    plt.savefig('p2_asymmetric_flows.png', dpi=300, bbox_inches='tight')
    print("Saved: p2_asymmetric_flows.png")
    
    print("\n=== Asymmetric Flows Results ===")
    for _, row in grouped.iterrows():
        delay = row['delay_c2_ms']
        jfi_mean = row['jfi_mean']
        jfi_std = row['jfi_std']
        print(f"Delay {delay:.0f}ms: JFI = {jfi_mean:.3f} ± {jfi_std:.3f}")

def plot_background_udp(csv_file):
    """Plot bar chart for UDP background traffic experiment"""
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    df.columns = df.columns.str.strip()
    
    # Map UDP off means to traffic condition labels
    condition_map = {1.5: 'Light', 0.8: 'Medium', 0.5: 'Heavy'}
    df['condition'] = df['udp_off_mean'].map(condition_map)
    
    grouped = df.groupby('condition').agg({
        'link_util': ['mean', 'std'],
        'jfi': ['mean', 'std']
    }).reset_index()
    
    # Flatten column names
    grouped.columns = ['condition', 'util_mean', 'util_std', 'jfi_mean', 'jfi_std']
    
    # Sort by condition
    condition_order = ['Light', 'Medium', 'Heavy']
    grouped['condition'] = pd.Categorical(grouped['condition'], categories=condition_order, ordered=True)
    grouped = grouped.sort_values('condition')
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    x = np.arange(len(grouped))
    width = 0.6
    
    # Plot link utilization
    bars1 = ax1.bar(x, grouped['util_mean'], width, 
                 yerr=grouped['util_std'], 
                    capsize=5, color=['#52B788', '#FCA311', '#E63946'], 
                    edgecolor='black', linewidth=1.5)
    ax1.set_xlabel('UDP Background Traffic Condition', fontsize=12)
    ax1.set_ylabel('Link Utilization', fontsize=12)
    ax1.set_title('Link Utilization with Background UDP Traffic', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(grouped['condition'])
    ax1.set_ylim([0, 1.2])
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=10)
    
    # Plot JFI
    bars2 = ax2.bar(x, grouped['jfi_mean'], width, 
                    yerr=grouped['jfi_std'],
                    capsize=5, color=['#52B788', '#FCA311', '#E63946'],
                    edgecolor='black', linewidth=1.5)
    ax2.set_xlabel('UDP Background Traffic Condition', fontsize=12)
    ax2.set_ylabel('Jain Fairness Index', fontsize=12)
    ax2.set_title('Fairness with Background UDP Traffic', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(grouped['condition'])
    ax2.set_ylim([0, 1.1])
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=10)
    
    plt.tight_layout()
    plt.savefig('p2_background_udp.png', dpi=300, bbox_inches='tight')
    print("Saved: p2_background_udp.png")
    
    print("\n=== Background UDP Results ===")
    for _, row in grouped.iterrows():
        condition = row['condition']
        util_mean = row['util_mean']
        util_std = row['util_std']
        jfi_mean = row['jfi_mean']
        jfi_std = row['jfi_std']
        print(f"{condition:8s}: Util = {util_mean:.3f} ± {util_std:.3f}, JFI = {jfi_mean:.3f} ± {jfi_std:.3f}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 analyze_p2.py <experiment_name>")
        print("Available experiments: fixed_bandwidth, varying_loss, asymmetric_flows, background_udp")
        sys.exit(1)
    
    exp_name = sys.argv[1]
    csv_file = f'p2_fairness_{exp_name}.csv'
    
    if not os.path.exists(csv_file):
        print(f"Error: CSV file {csv_file} not found")
        print(f"Run experiments first: sudo python3 p2_exp.py {exp_name}")
        sys.exit(1)
    
    print(f"\nAnalyzing results from {csv_file}...")
    
    if exp_name == 'fixed_bandwidth':
        plot_fixed_bandwidth(csv_file)
    elif exp_name == 'varying_loss':
        plot_varying_loss(csv_file)
    elif exp_name == 'asymmetric_flows':
        plot_asymmetric_flows(csv_file)
    elif exp_name == 'background_udp':
        plot_background_udp(csv_file)
    else:
        print(f"Unknown experiment: {exp_name}")
        sys.exit(1)
    
    print("\nAnalysis complete!")

if __name__ == "__main__":
    main()
