"""Poll live console status without owning or stopping any build workers."""
from contextlib import redirect_stdout
import io
import json
import subprocess
import sys
import time

from .tcl_arguments import tcl_word
from .log_analysis import enrich
from .run_output import run_tables


def console_info(console):
    """Read tmux metadata and request files without sending Tcl commands."""
    info = {'project': str(console.xpr), 'session': console.session,
            'log': str(console.logs_directory / 'vivado.log'), 'status': 'unavailable'}
    try:
        result = subprocess.run(
            ['tmux', 'list-panes', '-t', '=' + console.session, '-F',
             '#{pane_pid}\t#{pane_dead}\t#{pane_current_command}'],
            capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            pid, dead, command = result.stdout.splitlines()[0].split('\t', 2)
            info.update(pid=pid, command=command, status='exited' if dead == '1' else 'pane alive')
        pending = console.pending_request()
        info['request'] = str(pending) if pending else 'none pending'
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        info['detail'] = str(error)
    return info


def display_frame(records, info):
    print(f"Project XPR: {info['project']}")
    print(f"Tcl console: {info['status']} | pane PID: {info.get('pid', '-')} | command: {info.get('command', '-')}")
    print(f"tmux session: {info['session']}")
    print(f"Tcl request: {info.get('request', 'unknown')} (passive inspection)")
    print(f"Console log: {info['log']}")
    if info.get('detail'):
        print(f"Console inspection: {info['detail']}")
    run_tables(records)


def follow(console, group='', interval=5, once=False, machine=False, targets=None):
    if interval <= 0:
        raise ValueError('interval must be positive')
    with console.locked():
        console.open()
    command = f'lvp_open_project {tcl_word(console.xpr)}\nlvp_active_group_status {tcl_word(group)}'
    with console.locked():
        console.request(command)
    records = console.last_response.get('records', [])
    redraw = sys.stdout.isatty() and not once and not machine
    if redraw:
        sys.stdout.write('\033[?1049h\033[?25l')
        sys.stdout.flush()
    try:
        while records:
            response = enrich({'records': records}, log_only=True, targets=targets)
            info = console_info(console)
            if machine:
                response['console'] = info
                print(json.dumps(response), flush=True)
            elif redraw:
                frame = io.StringIO()
                with redirect_stdout(frame):
                    display_frame(response['records'], info)
                sys.stdout.write('\033[H\033[2J' + frame.getvalue())
                sys.stdout.flush()
            else:
                display_frame(response['records'], info)
            if response.get('analysis_error'):
                raise RuntimeError(response['analysis_error'])
            if once:
                return 0
            records = [row for row in response['records'] if not row['STATUS'].startswith('RUN_')]
            if not records:
                break
            time.sleep(interval)
        if not machine:
            print('No active runs remaining in the selected snapshot.')
        return 0
    except KeyboardInterrupt:
        if redraw:
            sys.stdout.write('\033[?25h\033[?1049l')
            sys.stdout.flush()
            redraw = False
        print('\nStopped following; console and builds remain running.')
        return 0
    finally:
        if redraw:
            sys.stdout.write('\033[?25h\033[?1049l')
            sys.stdout.flush()
