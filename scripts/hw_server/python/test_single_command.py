#!/usr/bin/env python3
"""
Test script to capture all output from a single Vivado TCL command
and detect the "Vivado% " prompt
"""

import subprocess
import select
import time
import sys
import os
import pty
import termios

def test_single_command():
    """Test a single command and log all output, looking for prompt"""
    
    log_file = f"vivado_test_log_{int(time.time())}.txt"
    log_fp = open(log_file, 'w')
    
    prompt = "Vivado% "
    
    print(f"Starting Vivado...")
    print(f"Log file: {log_file}")
    print(f"Looking for prompt: {repr(prompt)}")
    
    # Use pty to get TTY-like behavior (prompts appear on TTY)
    master_fd, slave_fd = pty.openpty()
    
    proc = subprocess.Popen(
        ['vivado', '-mode', 'tcl', '-nolog', '-nojournal'],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        text=True,
        bufsize=1,
        start_new_session=True
    )
    os.close(slave_fd)  # Close slave in parent process
    
    # Wait for startup and initial prompt
    print("Waiting for Vivado to start and show initial prompt...")
    log_fp.write("=== Waiting for initial prompt ===\n")
    
    output = ""
    buffer = ""
    start_time = time.time()
    prompt_found = False
    
    while time.time() - start_time < 10:
        elapsed = time.time() - start_time
        
        if proc.poll() is not None:
            log_fp.write(f"[PROCESS EXIT] After {elapsed:.2f}s\n")
            break
        
        ready, _, _ = select.select([master_fd], [], [], 0.1)
        
        if ready:
            if master_fd in ready:
                try:
                    data = os.read(master_fd, 4096).decode('utf-8', errors='replace')
                    if data:
                        output += data
                        buffer += data
                        log_fp.write(f"[TTY {elapsed:.3f}s] {repr(data)}\n")
                        log_fp.flush()
                        print(f"TTY: {repr(data)}")
                        
                        # Check for prompt
                        if prompt in data or prompt in buffer:
                            log_fp.write(f"[PROMPT FOUND] After {elapsed:.2f}s\n")
                            log_fp.flush()
                            print(f"*** PROMPT FOUND! ***")
                            prompt_found = True
                            break
                        
                        # Keep buffer reasonable
                        if len(buffer) > 100:
                            buffer = buffer[-100:]
                except Exception as e:
                    log_fp.write(f"[ERROR] {e}\n")
    
    if not prompt_found:
        log_fp.write(f"[NO PROMPT] After {time.time() - start_time:.2f}s\n")
        print("WARNING: Initial prompt not found")
    else:
        print("\nInitial prompt found! Now sending command...")
    
    # Send one simple command
    command = 'puts "hello world"'
    print(f"\nSending command: {command}")
    log_fp.write(f"\n=== Sending command: {command} ===\n")
    
    os.write(master_fd, (command + '\n').encode())
    
    # Read output until we see prompt again
    output = ""
    buffer = ""
    start_time = time.time()
    prompt_found = False
    
    log_fp.write(f"=== Reading output until prompt appears ===\n")
    
    while time.time() - start_time < 30:
        elapsed = time.time() - start_time
        
        if proc.poll() is not None:
            log_fp.write(f"[PROCESS EXIT] After {elapsed:.2f}s\n")
            break
        
        ready, _, _ = select.select([master_fd], [], [], 0.1)
        
        if ready:
            if master_fd in ready:
                try:
                    data = os.read(master_fd, 4096).decode('utf-8', errors='replace')
                    if data:
                        output += data
                        buffer += data
                        log_fp.write(f"[TTY {elapsed:.3f}s] {repr(data)}\n")
                        log_fp.flush()
                        print(f"TTY: {repr(data)}")
                        
                        # Check for prompt
                        if prompt in data or prompt in buffer:
                            log_fp.write(f"[PROMPT FOUND] After {elapsed:.2f}s\n")
                            log_fp.flush()
                            print(f"*** PROMPT FOUND! Command completed ***")
                            prompt_found = True
                            break
                        
                        # Keep buffer reasonable
                        if len(buffer) > 100:
                            buffer = buffer[-100:]
                except Exception as e:
                    log_fp.write(f"[ERROR] {e}\n")
        else:
            # No data - check if we should wait longer
            if elapsed > 5.0 and output:
                log_fp.write(f"[NO DATA] After {elapsed:.2f}s, assuming done\n")
                break
    
    if not prompt_found:
        log_fp.write(f"[NO PROMPT AFTER COMMAND] After {time.time() - start_time:.2f}s\n")
        print("WARNING: Prompt not found after command")
    
    log_fp.write(f"=== End of test (total time: {time.time() - start_time:.2f}s) ===\n")
    log_fp.close()
    
    # Cleanup
    try:
        os.write(master_fd, b'exit\n')
        proc.wait(timeout=2)
    except:
        proc.terminate()
    finally:
        os.close(master_fd)
    
    print(f"\nTest complete. Check log file: {log_file}")
    return log_file

if __name__ == "__main__":
    test_single_command()
