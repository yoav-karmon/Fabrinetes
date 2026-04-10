# HDLForge Documentation

This directory now follows a single-source-of-truth model for HDLForge API documentation.

## Canonical Document

- **[HDLForge.md](HDLForge.md)** - the only canonical HDLForge API document

It contains:

- CLI behavior
- project-file schema
- Verilator reference
- Vivado reference
- `LLM_orch` behavior
- internal architecture
- migration notes
- ownership boundaries between Fabrinetes and consuming repos

## Compatibility Pointer Files

These files remain only so older links do not break:

- [HDLForge-Verilator.md](HDLForge-Verilator.md)
- [HDLForge-Vivado.md](HDLForge-Vivado.md)
- [HDLForge-Architecture.md](HDLForge-Architecture.md)
- [HDLForge_v2_Migration_Guide.md](HDLForge_v2_Migration_Guide.md)

They should not become separate sources of truth again.

## Documentation Boundary

Use this rule when deciding where documentation belongs:

- generic HDLForge API and implementation behavior: `Fabrinetes`
- repo-specific HDLForge workflow: consuming repo
- `phy10gbaser` specifics: `fpga/fpga_projects/phy10gbaser`

Examples and project workflows should live with the project that uses HDLForge, not in this Fabrinetes API doc set.

## Related Documentation

- [Fabrinetes Main README](../../README.md)
- [Documentation Index](../DOCUMENTATION_INDEX.md)

