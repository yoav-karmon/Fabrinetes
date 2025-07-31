import re
import os
import sys

# Check if an argument is provided
if len(sys.argv) != 2:
    print("Usage: python3 extract_files.py <project.xpr>")
    sys.exit(1)

# Get the .xpr file from the argument
xpr_file = sys.argv[1]

# Check if the file exists
if not os.path.isfile(xpr_file):
    print(f"Error: File '{xpr_file}' not found.")
    sys.exit(1)

output_file = "sources_list.txt"

# Regex to extract file paths from the .xpr file
file_pattern = re.compile(r'(?<=<File Path=")(.*?)(?=")')

# Read the .xpr file and extract file paths
with open(xpr_file, "r") as f:
    file_paths = file_pattern.findall(f.read())

# Process files into structured data
file_data = []
for path in file_paths:
    file_name = os.path.basename(path)
    file_ext = os.path.splitext(file_name)[1]  # Extract file extension (.vhd, .v, .xdc, etc.)
    file_data.append((file_name, file_ext, path))

# Column widths for alignment
col_widths = [40, 10, 80]

# Write the table to file
with open(output_file, "w") as f:
    f.write("-" * sum(col_widths) + "\n")
    f.write(f"| {'File Name'.ljust(col_widths[0])} | {'Type'.ljust(col_widths[1])} | {'Path'.ljust(col_widths[2])} |\n")
    f.write("-" * sum(col_widths) + "\n")

    for file_name, file_ext, file_path in file_data:
        f.write(f"| {file_name.ljust(col_widths[0])} | {file_ext.ljust(col_widths[1])} | {file_path.ljust(col_widths[2])} |\n")

    f.write("-" * sum(col_widths) + "\n")

print(f"File list saved to: {output_file}")

