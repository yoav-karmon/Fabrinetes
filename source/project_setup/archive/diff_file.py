import sys
import os

if len(sys.argv) != 3:
    print("Usage: python3 compare_file_lists.py <file_list_1.txt> <file_list_2.txt>")
    sys.exit(1)

file1 = sys.argv[1]
file2 = sys.argv[2]

if not os.path.isfile(file1) or not os.path.isfile(file2):
    print("Error: One or both files not found.")
    sys.exit(1)

def extract_file_data(file_path):
    file_data = {}
    with open(file_path, "r") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) > 1:
                file_name = parts[1].strip()  # Extract filename (assuming table format)
                file_data[file_name] = line.strip()  # Store full line mapped to filename
    return file_data

file_data1 = extract_file_data(file1)
file_data2 = extract_file_data(file2)

only_in_file1 = set(file_data1.keys()) - set(file_data2.keys())
only_in_file2 = set(file_data2.keys()) - set(file_data1.keys())

print("\nLines only in", file1)
print("-" * 80)
for name in sorted(only_in_file1):
    print(file_data1[name])

print("\nLines only in", file2)
print("-" * 80)
for name in sorted(only_in_file2):
    print(file_data2[name])

