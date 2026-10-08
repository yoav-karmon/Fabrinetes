"""Attach read-only log details to non-project build status."""
import json
import os
from pathlib import Path
import subprocess
import sys


def enrich(response):
    records = response.get('records', [])
    if not any('running' in row.get('STATUS', '').lower() for row in records):
        return response
    script = Path(os.environ.get('REPO_TOP', '')) / 'tools/vivado_monitor/build_analysis.py'
    if not script.is_file():
        response['analysis_error'] = 'Project log analyzer was not found.'
        return response
    try:
        payload = dict(records=records)
        # A child Python process does not inherit this script's sys.path.
        # Let HDLForge expose its modules to the repository log analyzer.
        setup = Path(__file__).resolve().parent
        command = [str(setup / 'hdlforge'), '--env-python', json.dumps([str(setup)]),
                   'eval-cmd-argv', sys.executable, str(script)]
        result = subprocess.run(command, input=json.dumps(payload),
                                capture_output=True, text=True, check=True, timeout=30)
        response['records'] = json.loads(result.stdout)
    except subprocess.CalledProcessError as error:
        response['analysis_error'] = (error.stderr or '').strip() or str(error)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        response['analysis_error'] = str(error)
    return response
