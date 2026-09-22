"""One compact run-status table per synthesis group."""
from .terminal_output import table


def run_tables(records: list[dict]) -> bool:
    if not records or not all('NAME' in row and 'PARENT' in row and 'STATUS' in row for row in records):
        return False
    if any('STRATEGY' in row or 'FLOW' in row for row in records):
        return False
    groups = {}
    for row in records:
        groups.setdefault(row['PARENT'] or row['NAME'], []).append(row)
    for parent, rows in groups.items():
        print(f'\nGroup: {parent}')
        output = []
        for row in rows:
            status = row['STATUS']
            if status.lower().startswith('running'):
                status = 'Running'
            elif 'complete' in status.lower():
                status = 'Complete'
            metrics = ('WNS', 'TNS', 'WHS', 'THS')
            source = 'Vivado' if any(row.get('STATS.' + key) not in (None, '') for key in metrics) else 'log'
            prefix = 'STATS.' if source == 'Vivado' else 'LOG_'
            timing = [row.get(prefix + key, '') or '-' for key in metrics]
            if all(value == '-' for value in timing):
                source = '-'
            messages = '/'.join(str(row.get(key, '-')) for key in ('WARNINGS', 'CRITICAL_WARNINGS', 'ERRORS'))
            identity = [row.get('PID', '-'), row.get('PID_STATE', '-')] if any('PID' in item for item in rows) else []
            output.append([row['NAME'], *identity, status, row.get('PROGRESS', '-'), *timing, source, messages,
                           row.get('STATS.ELAPSED', '-'), row.get('LOG_AGE_SECONDS', '-')])
        identity_headers = ['PID', 'PID state'] if any('PID' in row for row in rows) else []
        table(['Run', *identity_headers, 'Status', '%', 'WNS', 'TNS', 'WHS', 'THS', 'Timing', 'W/CW/E', 'Elapsed', 'Idle(s)'], output, wrap=False)
        for row in rows:
            if row.get('LOG_STAGE'):
                print(f"{row['NAME']}: {row['LOG_STAGE']}")
    print('Timing in ns; log = intermediate estimate. W/CW/E = warnings/critical/errors; Idle = seconds since log update.')
    return True
