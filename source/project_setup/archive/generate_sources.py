import os
import argparse

def get_relative_paths(source_tcl, repo_top, output_file):
    relative_paths = []

    with open(source_tcl, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("read_vhdl -vhdl2008") or line.startswith("read_vhdl"):
                parts = line.split()  # Split by whitespace
                vhdl_path = parts[-1]  # The last element should be the path
                
                # Convert to absolute path if needed
                abs_path = os.path.abspath(vhdl_path)

                # Make it relative to REPO_TOP
                try:
                    rel_path = os.path.relpath(abs_path, repo_top)
                    relative_paths.append(rel_path)
                except ValueError:
                    print(f"Warning: Could not make {abs_path} relative to {repo_top}")

    # Write paths to output file
    with open(output_file, "w") as out_f:
        for path in relative_paths:
            out_f.write(f"$REPO_TOP/{path}\n")

    print(f"Generated {output_file} with {len(relative_paths)} entries.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate sources.txt from source.tcl")
    parser.add_argument("-t", "--tcl", required=True, help="Path to source.tcl")
    parser.add_argument("-r", "--repo", required=True, help="Path to REPO_TOP")
    parser.add_argument("-o", "--output", required=True, help="Path to sources.txt output")
    args = parser.parse_args()
    print(args)
    get_relative_paths(args.tcl, args.repo, args.output)
