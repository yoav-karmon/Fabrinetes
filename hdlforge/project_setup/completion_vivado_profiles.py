"""Describe Vivado profile actions without inspecting build artifacts."""


def profile_context(data: dict, candidate: str) -> tuple[str, dict, list[str]]:
    parts = candidate.rstrip(".").removeprefix("LLM_orch.").split(".")
    if len(parts) < 4 or parts[:3] != ["vivado", "build", "profile"]:
        return "", {}, []
    profiles = data.get("vivado", {}).get("config", {}).get("build_profiles", {})
    profile = profiles.get(parts[3], {})
    return parts[3], profile, parts[4:]


def profile_description(data: dict, candidate: str) -> str:
    name, profile, action = profile_context(data, candidate)
    if not profile:
        return ""
    descriptions = {
        "": f"Build actions for profile {name}",
        "synth": "Synthesis only",
        "synth.start": "Run synthesis only",
        "synth.reset": "Reset synthesis and invalidate dependent results",
        "impl": "All enabled implementations",
        "impl.start": "Run all enabled implementations; requires current synthesis",
        "impl.reset": "Reset all enabled implementations",
        "impl_and_bitstream": "All enabled implementations through bitstream",
        "impl_and_bitstream.start": "Run all enabled implementations through bitstream; requires current synthesis",
        "impl_and_bitstream.reset": "Reset all enabled implementations",
        "bitstream": "Bitstreams for all enabled implementations",
        "bitstream.start": "Generate bitstreams for all enabled implementations",
        "bitstream.reset": "Reset write_bitstream for all enabled implementations",
        "continue": "Continue synthesis and all enabled implementations through bitstream",
        "reset_and_full_rebuild": "Reset and rebuild synthesis and all enabled implementations through bitstream",
        "hal_env": "Print HAL environment configuration",
        "more_options": "Print synthesis options",
    }
    return descriptions.get(".".join(action), "")
