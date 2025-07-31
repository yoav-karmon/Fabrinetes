import matplotlib.pyplot as plt
import argparse

import numpy as np

def process_latency_file(file_path):
    latencies = []

    # Read the file and extract latency values (the "diff" field)
    with open(file_path, 'r') as file:
        for line in file:
            if 'diff=' in line:
                parts = line.strip().split(',')
                diff_part = next(part for part in parts if 'diff=' in part)
                diff_part = diff_part.replace('ns', '')  # Remove 'ns' if present
                latency = float(diff_part.split('=')[1])  # Extract the value of "diff"
                latency = round(latency, 3)  # Limit to 3 decimal places
                latencies.append(latency)

    # Calculate statistics using numpy
    latencies = np.array(latencies)
    min_latency = np.min(latencies)
    max_latency = np.max(latencies)
    percentiles = [1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 99]
    percentile_values = np.percentile(latencies, percentiles)

    # Display results
    print("Latency Statistics:")
    print(f"Min latency: {round(min_latency,3)}ns")
    for p, value in zip(percentiles, percentile_values):
        print(f"{p}% latency: {round(value,3)}ns")
    print(f"Max latency: {round(max_latency,3)}ns")

 

def extract_and_plot(file_path, output_file="output_graph.png", items=None, start_time=0):
    # Dictionaries to hold time and pre% values for each index
    def extract_csv_value(line, key):
        line = line.split(",")
        for item in line:
            if key in item:
                return item.split("=")[1]
        return None
    
    data = {item: {0: {'times': [], 'pre_values': []},
                   1: {'times': [], 'pre_values': []},
                   2: {'times': [], 'pre_values': []}} for item in items}

    # Read and process the log file
    with open(file_path, 'r') as file:
        for line in file:
            print(line)
            time_ns = float(extract_csv_value(line, "time"))
            value = float(extract_csv_value(line, "value"))
            item = extract_csv_value(line, "item")
            index = int(item.split("[")[1].split("]")[0])
            item = item.split("[")[0]
            if item in items:
                # Extract relevant data for specified items
                data[item][index]['times'].append(time_ns)
                data[item][index]['pre_values'].append(value)
    
    # Downsample the data for better visualization
    sample = 10000
    for item in data:
        for index in data[item]:
            if len(data[item][index]['times']) > sample:
                step = len(data[item][index]['times']) // sample
                data[item][index]['times'] = data[item][index]['times'][::step]
                data[item][index]['pre_values'] = data[item][index]['pre_values'][::step]

    # Plot the graph with specified colors and continuous lines
    plt.figure(figsize=(10, 6))
    colors = {0: 'red', 1: 'blue', 2: 'black'}  # Define colors for each index
    for item in data:
        for index in data[item]:
            if data[item][index]['times'] and data[item][index]['pre_values']:
                plt.plot(data[item][index]['times'], data[item][index]['pre_values'], color=colors[index], linestyle='-', label=f"{item}[{index}] [%]")

    # Customize the Y-axis ticks to reduce crowding
    plt.locator_params(axis='y', nbins=8)  # Set the number of Y-axis ticks (e.g., 8)

    plt.title("Items vs Time")
    plt.xlabel("Time (ns)")
    plt.ylabel("Pre (%)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file)
    plt.show()
    print(f"Graph saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse log file and plot header usage.")
    parser.add_argument("file_path", type=str, help="Path to the log file")
    parser.add_argument("--output", type=str, default="output_graph.png", help="Path to save the output graph")
    parser.add_argument("--items", type=str, help="List of items to search for in the log lines")
    args = parser.parse_args()

    extract_and_plot(args.file_path, args.output, args.items.split(","), 0)
