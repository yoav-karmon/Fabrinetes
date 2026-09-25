"""Render live run configuration and exposed stage properties in flow order."""

from .terminal_output import table


STAGE_ORDER = (
    "SYNTH_DESIGN", "INIT_DESIGN", "OPT_DESIGN", "POWER_OPT_DESIGN",
    "PLACE_DESIGN", "POST_PLACE_POWER_OPT_DESIGN", "PHYS_OPT_DESIGN",
    "ROUTE_DESIGN", "POST_ROUTE_PHYS_OPT_DESIGN", "WRITE_BITSTREAM",
    "WRITE_DEVICE_IMAGE",
)


def configuration_tables(records: list[dict]) -> bool:
    ###########################################################################
    # Group properties from each run without inferring defaults or enablement.
    # Keep the original records intact for JSON clients and verbose inspection.
    ###########################################################################
    if not records or not all("NAME" in row and "FLOW" in row for row in records):
        return False
    for record in records:
        metadata = []
        stages = {}
        for property_name, value in record.items():
            parts = property_name.split(".", 2)
            if len(parts) == 3 and parts[0] == "STEPS":
                stages.setdefault(parts[1], {})[parts[2]] = value
            else:
                metadata.append([property_name, value])
        print(f"\nRun: {record['NAME']}")
        table(["Property", "Value"], metadata)
        if not stages:
            continue
        ordered = [stage for stage in STAGE_ORDER if stage in stages]
        ordered.extend(sorted(set(stages) - set(ordered)))
        output = []
        for stage in ordered:
            properties = stages[stage]
            first = [name for name in ("IS_ENABLED", "ARGS.DIRECTIVE") if name in properties]
            names = first + sorted(set(properties) - set(first))
            for index, name in enumerate(names):
                value = properties[name]
                output.append([stage.lower() if index == 0 else "", name,
                               "(empty)" if value == "" else value])
        table(["Stage", "Property", "Value"], output)
    return True
