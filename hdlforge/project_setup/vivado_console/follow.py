"""Poll live console status without owning or stopping any build workers."""
import time
import json

from .tcl_arguments import tcl_word
from .log_analysis import enrich
from .run_output import run_tables


def follow(console, group='', interval=5, once=False, machine=False, targets=None):
    if interval <= 0:
        raise ValueError('interval must be positive')
    with console.locked():
        console.open()
    command = f'lvp_open_project {tcl_word(console.xpr)}\nlvp_active_group_status {tcl_word(group)}'
    with console.locked():
        console.request(command)
    records = console.last_response.get('records', [])
    try:
        while records:
            response = enrich({'records': records}, log_only=True, targets=targets)
            if machine:
                print(json.dumps(response), flush=True)
            else:
                run_tables(response['records'])
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
        print('\nStopped following; console and builds remain running.')
        return 0
