#!/usr/bin/env python3
import io
import sys
import os
import argparse
from os.path import expanduser
from io import StringIO


repo_top_relative_from_env = os.getenv("REPO_TOP_REL")
repo_top_from_env = os.getenv("REPO_TOP")
sys.path.append(repo_top_from_env+"/tools/scripts/py")
import collect_source as collect_source

# cmd line call
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='build for simulation or implementation')
    parser.add_argument('-t', '--top_level', type=str, help='path to top level module')
    parser.add_argument('-o', '--output', type=str, help='sources file out file path')


    args = parser.parse_args()
    ########




    # Check for the environment variable REPO_TOP
    repo_top = os.getenv('REPO_TOP')
    
    repo_top_relative_from_env = os.getenv("REPO_TOP_REL")
    repo_top_from_env = os.getenv("REPO_TOP")

    # Raise an error if REPO_TOP is not set
    if repo_top_from_env is None:
        raise EnvironmentError("Error: REPO_TOP environment variable is not set. Please set it and try again.")


    if repo_top_relative_from_env is None:
        raise EnvironmentError("Error: REPO_TOP_REL environment variable is not set. Please set it and try again.")

    



    #####################
    # call build script #
    #####################
    WORKSPACE_ROOT=repo_top_from_env
    BOARD_ID=11
    IP_SUBDIR="VUP"
    APP_ID=239
    APP_CFG= 0
    TOP_LEVEL_MODULE=args.top_level 
    FUNC_SIM= "True"
    VIVADO_BIN_PATH="/data/Xilinx/Vivado/2021.2/bin"
    INCLUDE_COMMON='True'
    verbose=True

    def parse_collect_source_output_from_console():

        # Redirect console output to a string buffer
        buffer = io.StringIO()
        sys.stdout = buffer

        collect_source.collect_cocotb_sim_source(WORKSPACE_ROOT, BOARD_ID, IP_SUBDIR, APP_ID, APP_CFG, TOP_LEVEL_MODULE, FUNC_SIM, VIVADO_BIN_PATH, INCLUDE_COMMON, verbose)




        # Retrieve the content from the buffer
        output = buffer.getvalue()
        buffer.close()
        # Now parse the collected output
        lines = output.splitlines()
        collected = False
        result = []


        for line in lines:
            # Check if we reached the start of the relevant data
            if  "Collected HDL source files" in line.strip() :
                collected = True
                continue
            # Collect lines only after the relevant line is found
            if collected and line.strip():
                file_path = eval(line.strip())[1]
                result.append(file_path)

        return result
    
    original_stdout = sys.stdout  # Save the original stdout
    sys.stdout = StringIO()       # Redirect stdout to a dummy StringIO buffer
    parsed_list = parse_collect_source_output_from_console()
    sys.stdout = original_stdout # Reset stdout
    with open(f"{args.output}", 'w') as f:
        for item in parsed_list:
            f.write(f"$REPO_TOP{item}\n")


