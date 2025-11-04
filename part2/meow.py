
#!/usr/bin/env python3
"""
Compare experimental results against benchmarks with colored output.
Shows side-by-side comparison of your results vs benchmarks.
"""

import sys
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ANSI color codes
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'

# Benchmarks from part2.txt
BENCHMARKS = {
    'fixed_bandwidth': {
        # bw: (link_util, jfi)
        100: (0.54, 0.99),
        200: (0.29, 0.99),
        300: (0.19, 0.99),
        400: (0.17, 0.99),
        500: (0.13, 0.99),
        600: (0.10, 0.99),
        700: (0.10, 0.99),
        800: (0.058, 0.99),
        900: (0.055, 0.99),
        1000: (0.056, 0.99),
    },
    'varying_loss': {
        # loss: (link_util, jfi)
        0.0: (0.54, 0.99),  # Added from fixed_bandwidth at 0% loss
        0.5: (0.068, 0.99),
        1.0: (0.035, 0.99),
        1.5: (0.023, 0.99),
        2.0: (0.017, 0.99),
    },
    'asymmetric_flows': {
        # delay_c2_ms: (link_util, jfi)
        5: (0.54, 0.99),
        10: (0.55, 0.97),
        15: (0.51, 0.92),
        20: (0.55, 0.83),
        25: (0.54, 0.80),
    },
    'background_udp': {
        # udp_off_mean: (link_util, jfi)
        0.5: (0.099, 0.99),
        0.8: (0.17, 0.99),
        1.5: (0.25, 0.99),
    }
}

# Thresholds for comparison
UTIL_TOLERANCE = 0.02  # ±5% is considered similar
JFI_TOLERANCE = 0.03   # ±3% is considered similar


def colorize(text: str, color: str, bold: bool = False) -> str:
    """Wrap text with ANSI color codes."""
    prefix = Colors.BOLD if bold else ''
    return f"{prefix}{color}{text}{Colors.RESET}"


def compare_value(your_val: float, bench_val: float, tolerance: float, higher_is_better: bool = True) -> Tuple[str, str]:
    """
    Compare your value against benchmark.
    Returns: (color, status_symbol)
    """
    diff = your_val - bench_val
    diff_pct = (diff / bench_val * 100) if bench_val != 0 else 0
    
    if abs(diff) <= tolerance:
        return Colors.YELLOW, "≈"  # Similar
    
    if higher_is_better:
        if diff > 0:
            return Colors.GREEN, "↑"  # Better (ahead)
        else:
            return Colors.RED, "↓"  # Worse (lacking)
    else:
        if diff < 0:
            return Colors.GREEN, "↑"  # Better
        else:
            return Colors.RED, "↓"  # Worse
    

def parse_csv_results(filepath: Path, key_col: str, avg_cols: List[str]) -> Dict[float, Tuple[float, ...]]:
    """
    Parse CSV file and compute averages across iterations.
    Returns dict: {key_value: (avg_metric1, avg_metric2, ...)}
    """
    if not filepath.exists():
        return {}
    
    data_by_key: Dict[float, List[List[float]]] = {}
    
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        # Strip whitespace from column names
        reader.fieldnames = [name.strip() if name else name for name in reader.fieldnames]
        
        for row in reader:
            try:
                # Strip whitespace from keys too
                row = {k.strip(): v.strip() if v else v for k, v in row.items()}
                
                key_val = float(row[key_col])
                metrics = [float(row[col]) for col in avg_cols]
                
                if key_val not in data_by_key:
                    data_by_key[key_val] = []
                data_by_key[key_val].append(metrics)
            except (ValueError, KeyError) as e:
                continue
    
    # Compute averages
    result = {}
    for key_val, metric_lists in data_by_key.items():
        num_metrics = len(metric_lists[0])
        num_samples = len(metric_lists)
        
        averages = []
        for i in range(num_metrics):
            avg = sum(sample[i] for sample in metric_lists) / num_samples
            averages.append(avg)
        
        result[key_val] = tuple(averages)
    
    return result


def print_section_header(title: str):
    """Print a formatted section header."""
    line = "=" * 80
    print(f"\n{colorize(line, Colors.CYAN, bold=True)}")
    print(f"{colorize(title.center(80), Colors.CYAN, bold=True)}")
    print(f"{colorize(line, Colors.CYAN, bold=True)}\n")


def print_comparison_table(exp_name: str, key_name: str, your_results: Dict, 
                           benchmarks: Dict, metric_names: List[str]):
    """Print side-by-side comparison table."""
    
    # Table header
    print(f"{colorize('Parameter', Colors.BOLD, bold=True):>12} | ", end="")
    for metric in metric_names:
        print(f"{colorize(f'Your {metric}', Colors.BOLD, bold=True):>15} | ", end="")
        print(f"{colorize(f'Bench {metric}', Colors.BOLD, bold=True):>15} | ", end="")
        print(f"{colorize('Status', Colors.BOLD, bold=True):>8} | ", end="")
    print()
    print("-" * (14 + len(metric_names) * 42))
    
    # Get all keys (union of yours and benchmark)
    all_keys = sorted(set(list(your_results.keys()) + list(benchmarks.keys())))
    
    ahead_count = 0
    behind_count = 0
    similar_count = 0
    
    for key in all_keys:
        print(f"{key:>12.2f} | ", end="")
        
        your_vals = your_results.get(key)
        bench_vals = benchmarks.get(key)
        
        if your_vals is None:
            # Missing your results
            for i, metric in enumerate(metric_names):
                print(f"{colorize('MISSING', Colors.RED):>15} | ", end="")
                if bench_vals:
                    print(f"{bench_vals[i]:>15.4f} | ", end="")
                else:
                    print(f"{'N/A':>15} | ", end="")
                print(f"{colorize('✗', Colors.RED):>8} | ", end="")
            behind_count += 1
        elif bench_vals is None:
            # No benchmark (extra test case)
            for i, metric in enumerate(metric_names):
                print(f"{your_vals[i]:>15.4f} | ", end="")
                print(f"{colorize('N/A', Colors.BLUE):>15} | ", end="")
                print(f"{colorize('?', Colors.BLUE):>8} | ", end="")
        else:
            # Compare each metric
            for i, metric in enumerate(metric_names):
                your_val = your_vals[i]
                bench_val = bench_vals[i]
                
                # Link utilization: higher is better
                # JFI: higher is better
                tolerance = UTIL_TOLERANCE if 'util' in metric.lower() else JFI_TOLERANCE
                color, symbol = compare_value(your_val, bench_val, tolerance, higher_is_better=True)
                
                print(f"{colorize(f'{your_val:.4f}', color):>15} | ", end="")
                print(f"{bench_val:>15.4f} | ", end="")
                print(f"{colorize(symbol, color, bold=True):>8} | ", end="")
                
                # Count status
                if symbol == "↑":
                    ahead_count += 1
                elif symbol == "↓":
                    behind_count += 1
                else:
                    similar_count += 1
        
        print()
    
    # Summary
    print("-" * (14 + len(metric_names) * 42))
    total = ahead_count + behind_count + similar_count
    if total > 0:
        print(f"\n{colorize('Summary:', Colors.BOLD, bold=True)}")
        print(f"  {colorize('↑ Ahead:', Colors.GREEN)} {ahead_count}/{total} ({ahead_count/total*100:.1f}%)")
        print(f"  {colorize('↓ Behind:', Colors.RED)} {behind_count}/{total} ({behind_count/total*100:.1f}%)")
        print(f"  {colorize('≈ Similar:', Colors.YELLOW)} {similar_count}/{total} ({similar_count/total*100:.1f}%)")


def analyze_experiment(exp_name: str, csv_filename: str, key_col: str, 
                       metric_cols: List[str], metric_names: List[str]):
    """Analyze a single experiment."""
    print_section_header(f"Experiment: {exp_name.upper().replace('_', ' ')}")
    
    csv_path = Path(csv_filename)
    your_results = parse_csv_results(csv_path, key_col, metric_cols)
    benchmarks = BENCHMARKS[exp_name]
    
    if not your_results:
        print(f"{colorize('ERROR: No results found in', Colors.RED)} {csv_filename}")
        print(f"{colorize('Make sure the CSV file exists and has data.', Colors.RED)}")
        return
    
    print(f"Loaded {len(your_results)} data points from {colorize(csv_filename, Colors.BLUE)}")
    print(f"Comparing against {len(benchmarks)} benchmark points\n")
    
    print_comparison_table(exp_name, key_col, your_results, benchmarks, metric_names)


def main():
    """Main function to run all comparisons."""
    print(colorize("\n" + "█" * 80, Colors.MAGENTA, bold=True))
    print(colorize("PART 2 RESULTS COMPARISON TOOL".center(80), Colors.MAGENTA, bold=True))
    print(colorize("█" * 80 + "\n", Colors.MAGENTA, bold=True))
    
    print(f"{colorize('Legend:', Colors.BOLD, bold=True)}")
    print(f"  {colorize('↑ Green', Colors.GREEN)} = Your results are BETTER than benchmark (ahead)")
    print(f"  {colorize('↓ Red', Colors.RED)} = Your results are WORSE than benchmark (lacking)")
    print(f"  {colorize('≈ Yellow', Colors.YELLOW)} = Your results are SIMILAR to benchmark (within tolerance)")
    print(f"  {colorize('? Blue', Colors.BLUE)} = No benchmark available for this parameter")
    
    # Experiment 1: Fixed Bandwidth
    analyze_experiment(
        'fixed_bandwidth',
        'p2_fairness_fixed_bandwidth.csv',
        'bw',
        ['link_util', 'jfi'],
        ['Util', 'JFI']
    )
    
    # Experiment 2: Varying Loss
    analyze_experiment(
        'varying_loss',
        'p2_fairness_varying_loss.csv',
        'loss',
        ['link_util', 'jfi'],
        ['Util', 'JFI']
    )
    
    # Experiment 3: Asymmetric Flows
    analyze_experiment(
        'asymmetric_flows',
        'p2_fairness_asymmetric_flows.csv',
        'delay_c2_ms',
        ['link_util', 'jfi'],
        ['Util', 'JFI']
    )
    
    # Experiment 4: Background UDP
    analyze_experiment(
        'background_udp',
        'p2_fairness_background_udp.csv',
        'udp_off_mean',
        ['link_util', 'jfi'],
        ['Util', 'JFI']
    )
    
    print(colorize("\n" + "█" * 80, Colors.MAGENTA, bold=True))
    print(colorize("ANALYSIS COMPLETE".center(80), Colors.MAGENTA, bold=True))
    print(colorize("█" * 80 + "\n", Colors.MAGENTA, bold=True))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{colorize('Interrupted by user', Colors.YELLOW)}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{colorize(f'Error: {e}', Colors.RED)}")
        sys.exit(1)
