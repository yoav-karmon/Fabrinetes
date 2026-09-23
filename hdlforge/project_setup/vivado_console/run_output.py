"""One compact run-status table per synthesis group."""
import shlex

from .terminal_output import table


def run_tables(records: list[dict]) -> bool:
    if not records or not all('NAME' in row and 'PARENT' in row and 'STATUS' in row for row in records):
        return False
    if any('STRATEGY' in row or 'FLOW' in row for row in records):
        return False
    groups = {}
    for row in records:
        groups.setdefault(row['PARENT'] or row['NAME'], []).append(row)
    sources = {}
    for row in records:
        if 'WORKER_STATS' in row:
            sources.setdefault(row['WORKER_STATS'].get('source', 'unavailable'), []).append(row['NAME'])
    if sources:
        summary = next(iter(sources)) if len(sources) == 1 else '; '.join(
            f"{source}: {', '.join(names)}" for source, names in sources.items())
        print(f'Stats source: {summary}')
    for parent, rows in groups.items():
        print(f'\nGroup: {parent}')
        output = []
        worker_keys = ('cpu', 'rss', 'peak', 'state', 'threads')
        worker_headers = ['CPU time', 'RSS(MB)', 'Peak(MB)', 'State', 'Threads'] if any('WORKER_STATS' in row for row in rows) else []
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
            worker = [row.get('WORKER_STATS', {}).get(key, '-') for key in worker_keys] if worker_headers else []
            output.append([row['NAME'], *identity, status, row.get('PROGRESS', '-'), *timing, source, messages,
                           row.get('WORKER_STATS', {}).get('elapsed', row.get('STATS.ELAPSED', '-')), row.get('LOG_AGE_SECONDS', '-'), *worker])
        identity_headers = ['PID', 'PID state'] if any('PID' in row for row in rows) else []
        table(['Run', *identity_headers, 'Status', '%', 'WNS', 'TNS', 'WHS', 'THS', 'Timing', 'W/CW/E', 'Elapsed', 'Idle(s)', *worker_headers], output, wrap=False)
    for row in records:
        if row.get('LOG_PATH'):
            print(f"\n{row['NAME']} log: {row['LOG_PATH']}")
            print(f"tail -n 5 -f -- {shlex.quote(row['LOG_PATH'])}")
            tail = '\n'.join(row['LOG_TAIL']) if row.get('LOG_TAIL') else '(log empty or unavailable)'
            table([f"{row['NAME']} | Last 5 log lines"], [[tail]])
    return True
