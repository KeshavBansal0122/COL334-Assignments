#!/usr/bin/env python3
"""
Part 1 Results Analysis and Visualization
Generates plots from experiment CSV files
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys
import os

def plot_loss_experiment(csv_file):
    """Plot download time vs loss rate"""
    df = pd.read_csv(csv_file)
    
    # Group by loss rate and calculate statistics
    grouped = df.groupby('loss').agg({
        'ttc': ['mean', 'std', 'count']
    }).reset_index()
    
    # Calculate 90% confidence interval (z=1.645)
    grouped['ci'] = 1.645 * grouped['ttc']['std'] / np.sqrt(grouped['ttc']['count'])
    
    # Flatten column names for easier access
    grouped.columns = ['loss', 'mean', 'std', 'count', 'ci']
    
    plt.figure(figsize=(10, 6))
    plt.errorbar(grouped['loss'], grouped['mean'], 
                 yerr=grouped['ci'], 
                 marker='o', capsize=5, linewidth=2, markersize=8,
                 color='#E63946', label='Download Time')
    
    plt.xlabel('Packet Loss Rate (%)', fontsize=12)
    plt.ylabel('Download Time (seconds)', fontsize=12)
    plt.title('Impact of Packet Loss on Download Time', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig('part1_loss_results.png', dpi=300, bbox_inches='tight')
    print("Saved: part1_loss_results.png")
    
    # Print statistics
    print("\n=== Loss Rate Experiment Results ===")
    for _, row in grouped.iterrows():
        loss = row['loss']
        mean = row['mean']
        ci = row['ci']
        print(f"Loss {loss:.1f}%: {mean:.3f}s ± {ci:.3f}s (90% CI)")

def plot_jitter_experiment(csv_file):
    """Plot download time vs delay jitter"""
    df = pd.read_csv(csv_file)
    
    # Group by jitter and calculate statistics
    grouped = df.groupby('jitter').agg({
        'ttc': ['mean', 'std', 'count']
    }).reset_index()
    
    # Calculate 90% confidence interval
    grouped['ci'] = 1.645 * grouped['ttc']['std'] / np.sqrt(grouped['ttc']['count'])
    
    # Flatten column names for easier access
    grouped.columns = ['jitter', 'mean', 'std', 'count', 'ci']
    
    plt.figure(figsize=(10, 6))
    plt.errorbar(grouped['jitter'], grouped['mean'], 
                 yerr=grouped['ci'], 
                 marker='s', capsize=5, linewidth=2, markersize=8,
                 color='#06A77D', label='Download Time')
    
    plt.xlabel('Delay Jitter (ms)', fontsize=12)
    plt.ylabel('Download Time (seconds)', fontsize=12)
    plt.title('Impact of Delay Jitter on Download Time', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig('part1_jitter_results.png', dpi=300, bbox_inches='tight')
    print("Saved: part1_jitter_results.png")
    
    # Print statistics
    print("\n=== Delay Jitter Experiment Results ===")
    for _, row in grouped.iterrows():
        jitter = row['jitter']
        mean = row['mean']
        ci = row['ci']
        print(f"Jitter {jitter:.0f}ms: {mean:.3f}s ± {ci:.3f}s (90% CI)")

def plot_combined(loss_csv, jitter_csv):
    """Plot both experiments in one figure"""
    df_loss = pd.read_csv(loss_csv)
    df_jitter = pd.read_csv(jitter_csv)
    
    # Process loss data
    grouped_loss = df_loss.groupby('loss').agg({
        'ttc': ['mean', 'std', 'count']
    }).reset_index()
    grouped_loss['ci'] = 1.645 * grouped_loss['ttc']['std'] / np.sqrt(grouped_loss['ttc']['count'])
    
    # Process jitter data
    grouped_jitter = df_jitter.groupby('jitter').agg({
        'ttc': ['mean', 'std', 'count']
    }).reset_index()
    grouped_jitter['ci'] = 1.645 * grouped_jitter['ttc']['std'] / np.sqrt(grouped_jitter['ttc']['count'])
    
    # Create combined plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Loss plot
    ax1.errorbar(grouped_loss['loss'], grouped_loss['ttc']['mean'], 
                 yerr=grouped_loss['ci'], 
                 marker='o', capsize=5, linewidth=2, markersize=8,
                 color='#E63946', label='Download Time')
    ax1.set_xlabel('Packet Loss Rate (%)', fontsize=12)
    ax1.set_ylabel('Download Time (seconds)', fontsize=12)
    ax1.set_title('Impact of Packet Loss', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Jitter plot
    ax2.errorbar(grouped_jitter['jitter'], grouped_jitter['ttc']['mean'], 
                 yerr=grouped_jitter['ci'], 
                 marker='s', capsize=5, linewidth=2, markersize=8,
                 color='#06A77D', label='Download Time')
    ax2.set_xlabel('Delay Jitter (ms)', fontsize=12)
    ax2.set_ylabel('Download Time (seconds)', fontsize=12)
    ax2.set_title('Impact of Delay Jitter', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    plt.savefig('part1_combined_results.png', dpi=300, bbox_inches='tight')
    print("Saved: part1_combined_results.png")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_p1.py <experiment_type>")
        print("Available types: loss, jitter, combined")
        print("\nExamples:")
        print("  python3 analyze_p1.py loss")
        print("  python3 analyze_p1.py jitter")
        print("  python3 analyze_p1.py combined")
        sys.exit(1)
    
    exp_type = sys.argv[1]
    
    if exp_type == 'loss':
        csv_file = 'reliability_loss.csv'
        if not os.path.exists(csv_file):
            print(f"Error: {csv_file} not found")
            print("Run experiment first: sudo python3 p1_exp.py loss")
            sys.exit(1)
        plot_loss_experiment(csv_file)
        
    elif exp_type == 'jitter':
        csv_file = 'reliability_jitter.csv'
        if not os.path.exists(csv_file):
            print(f"Error: {csv_file} not found")
            print("Run experiment first: sudo python3 p1_exp.py jitter")
            sys.exit(1)
        plot_jitter_experiment(csv_file)
        
    elif exp_type == 'combined':
        loss_csv = 'reliability_loss.csv'
        jitter_csv = 'reliability_jitter.csv'
        
        if not os.path.exists(loss_csv) or not os.path.exists(jitter_csv):
            print("Error: One or both CSV files not found")
            print("Run both experiments first:")
            print("  sudo python3 p1_exp.py loss")
            print("  sudo python3 p1_exp.py jitter")
            sys.exit(1)
        
        plot_combined(loss_csv, jitter_csv)
        plot_loss_experiment(loss_csv)
        plot_jitter_experiment(jitter_csv)
    else:
        print(f"Unknown experiment type: {exp_type}")
        sys.exit(1)
    
    print("\nAnalysis complete!")

if __name__ == "__main__":
    main()
