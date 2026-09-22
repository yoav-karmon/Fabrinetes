"""Attach project-owned log details while retaining authoritative Tcl status."""
import json
import os
from pathlib import Path
import subprocess
import sys


def enrich(response, log_only=False, targets=None):
    records = response.get('records', [])
    if not log_only and not any('running' in row.get('STATUS', '').lower() for row in records):
        return response
    script = Path(os.environ.get('REPO_TOP', '')) / 'tools/vivado_monitor/console_analysis.py'
    if not script.is_file():
        response['analysis_error'] = 'Project log analyzer was not found.'
        return response
    try:
        payload = dict(records=records, log_only=log_only, targets=targets or {})
        result = subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                                capture_output=True, text=True, check=True, timeout=30)
        response['records'] = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        response['analysis_error'] = str(error)
    return response
