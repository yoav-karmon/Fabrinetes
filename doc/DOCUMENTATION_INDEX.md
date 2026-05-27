# Fabrinetes Documentation Index

## Overview

This document provides a comprehensive index of all documentation files in the Fabrinetes project, organized by category and purpose.

## Documentation Structure

```
Fabrinetes/
├── README.md                          # Main project README
├── doc/                               # Documentation root
│   ├── DOCUMENTATION_INDEX.md         # This file
│   ├── README.md                      # Documentation overview
│   ├── bug-prevention-guide.md        # Bug prevention strategies
│   ├── container-doc/                 # Container-specific documentation
│   │   ├── architecture.md
│   │   ├── container-path-management.md
│   │   ├── devcontainer-cli.md
│   │   ├── docker-installation.md
│   │   ├── testing_guide.md
│   │   ├── container-hdlforge-test.md
│   │   └── github-container-registry.md
│   └── hdlforge-doc/                  # HDLForge build system documentation
│       ├── README.md                  # HDLForge documentation guide
│       ├── HDLForge.md                # Canonical HDLForge API reference
│       ├── HDLForge-Verilator.md      # Compatibility pointer
│       ├── HDLForge-Vivado.md         # Compatibility pointer
│       ├── HDLForge-Architecture.md   # Compatibility pointer
│       └── HDLForge_v2_Migration_Guide.md
└── examples/                          # Example projects
    ├── README.md
    └── addr_32bit/README.md
```

---

## Core Documentation

### Main Documentation
- **[Project README](../README.md)** - Main project documentation with quick start guide, features, and usage examples
- **[Documentation Overview](README.md)** - Overview of Fabrinetes documentation

### Architecture & Design
- **[Architecture Documentation](container-doc/architecture.md)** - Core architecture, design principles, and system components
- **[Container Path Management](container-doc/container-path-management.md)** - Comprehensive guide to the two-level path management system

### Development
- **[Bug Prevention Guide](bug-prevention-guide.md)** - Common issues and prevention strategies

---

## User Guides

### Getting Started
- **[Docker Installation](container-doc/docker-installation.md)** - Docker setup and installation guide
- **[Dev Containers CLI Launch](container-doc/devcontainer-cli.md)** - Install Dev Containers CLI, launch repo-owned `.devcontainer` configs, attach, exec, stop, and recreate
- **[Testing Guide](container-doc/testing_guide.md)** - Devcontainer verification procedures
- **[Container Path Management](container-doc/container-path-management.md)** - Understanding the path system

### Container Management
- **[Architecture Documentation](container-doc/architecture.md)** - Container architecture and design
- **[Dev Containers CLI Launch](container-doc/devcontainer-cli.md)** - Recommended project launch path using VS Code/Cursor Dev Containers or `devcontainer up`
- **[Docker Installation](container-doc/docker-installation.md)** - Docker setup
- **[Container HDLForge Test](container-doc/container-hdlforge-test.md)** - Testing HDLForge in container environments
- **[GitHub Container Registry](container-doc/github-container-registry.md)** - Container registry setup and usage

---

## HDLForge Build System

> **📁 Complete HDLForge Documentation:** [hdlforge-doc/README.md](hdlforge-doc/README.md)

### Quick Links
- **[HDLForge API Reference](hdlforge-doc/HDLForge.md)** - Single HDLForge source of truth for CLI, schema, Verilator, Vivado, architecture, and migration
- **[Verilator Pointer](hdlforge-doc/HDLForge-Verilator.md)** - Compatibility pointer to the canonical API reference
- **[Vivado Pointer](hdlforge-doc/HDLForge-Vivado.md)** - Compatibility pointer to the canonical API reference
- **[Architecture Pointer](hdlforge-doc/HDLForge-Architecture.md)** - Compatibility pointer to the canonical API reference
- **[Migration Pointer](hdlforge-doc/HDLForge_v2_Migration_Guide.md)** - Compatibility pointer to the canonical API reference

---

## Examples & Templates

### Example Projects
- **[Examples Overview](../examples/README.md)** - Example projects and usage patterns
- **[Address 32-bit Example](../examples/addr_32bit/README.md)** - Specific example project documentation

### Container Templates
- **[Container Templates](../containers/)** - Pre-built container configurations and templates

---

## Quick Navigation by User Type

### 🆕 New Users
**Start here:**
1. [Project README](../README.md) - Project overview and quick start
2. [Docker Installation](container-doc/docker-installation.md) - Set up Docker
3. [Dev Containers CLI Launch](container-doc/devcontainer-cli.md) - Start a repo-owned devcontainer
4. [Container Path Management](container-doc/container-path-management.md) - Understand the path system
5. [Testing Guide](container-doc/testing_guide.md) - Verify the devcontainer

### 👨‍💻 Developers
**Essential reads:**
- [Architecture Documentation](container-doc/architecture.md) - System design and components
- [Bug Prevention Guide](bug-prevention-guide.md) - Common pitfalls and solutions
- [Dev Containers CLI Launch](container-doc/devcontainer-cli.md) - Container launch and attach flow

### ⚙️ FPGA/HDL Developers
**HDLForge workflow:**
1. [HDLForge API Reference](hdlforge-doc/HDLForge.md) - Build system CLI, schema, Verilator, Vivado, and internals
2. Project-specific HDLForge usage - see the consuming project repository docs

### 🚀 Advanced Users
**Deep dives:**
- [HDLForge API Reference](hdlforge-doc/HDLForge.md#7-internal-architecture) - Internal implementation
- [GitHub Container Registry](container-doc/github-container-registry.md) - Container distribution
- [Container HDLForge Test](container-doc/container-hdlforge-test.md) - Advanced testing

---

## Quick Navigation by Topic

### 🐳 Container Management
| Document | Purpose |
|----------|---------|
| [Architecture](container-doc/architecture.md) | Core container architecture and design |
| [Path Management](container-doc/container-path-management.md) | Two-level path system explained |
| [Dev Containers CLI Launch](container-doc/devcontainer-cli.md) | Recommended launch path for `.devcontainer` projects |
| [Docker Installation](container-doc/docker-installation.md) | Docker setup and configuration |
| [Container Registry](container-doc/github-container-registry.md) | GHCR setup and usage |

### 🔧 Build System (HDLForge)
| Document | Purpose |
|----------|---------|
| [HDLForge API Reference](hdlforge-doc/HDLForge.md) | Single source of truth for HDLForge API and internals |
| [Verilator Pointer](hdlforge-doc/HDLForge-Verilator.md) | Compatibility pointer to the canonical API reference |
| [Vivado Pointer](hdlforge-doc/HDLForge-Vivado.md) | Compatibility pointer to the canonical API reference |
| [Architecture Pointer](hdlforge-doc/HDLForge-Architecture.md) | Compatibility pointer to the canonical API reference |

### 🧪 Testing & Quality
| Document | Purpose |
|----------|---------|
| [Testing Guide](container-doc/testing_guide.md) | Devcontainer verification procedures |
| [Bug Prevention](bug-prevention-guide.md) | Common issues and prevention |
| [Container HDLForge Test](container-doc/container-hdlforge-test.md) | HDLForge container testing |

### 📚 Launch & Examples
| Document | Purpose |
|----------|---------|
| [Dev Containers CLI Launch](container-doc/devcontainer-cli.md) | Devcontainer launch and attach flow |
| [Examples](../examples/README.md) | Example projects and patterns |

---

## Documentation Standards

### File Organization
- **`doc/`** - Main documentation directory
  - **`container-doc/`** - Container-specific documentation
  - **`hdlforge-doc/`** - HDLForge build system documentation
- **`examples/`** - Example projects with README.md per example

### Naming Conventions
- **README.md** - Primary documentation for directories
- **kebab-case.md** - Descriptive filenames (e.g., `bug-prevention-guide.md`)
- **Subdirectories** - Organize related documentation (e.g., `hdlforge-doc/`)

### Content Standards
- **Markdown Format** - All documentation in Markdown (.md) format
- **Consistent Structure** - Use headers (H1, H2, etc.), code blocks, tables
- **Cross-References** - Link to related documentation
- **Examples** - Include practical examples and usage patterns
- **Troubleshooting** - Document common issues and solutions

### Maintenance Guidelines
- **Keep Updated** - Documentation should reflect current code
- **Version Control** - All documentation tracked in Git
- **Review Process** - Documentation changes reviewed like code
- **User Feedback** - Incorporate feedback and questions

---

## Contributing to Documentation

### Adding New Documentation
1. **Determine Category** - Choose appropriate directory (`doc/`, `doc/container-doc/`, `doc/hdlforge-doc/`, `examples/`)
2. **Follow Standards** - Use consistent naming and formatting
3. **Cross-Reference** - Link to related documentation
4. **Update Index** - Add entry to this index file

### Updating Existing Documentation
1. **Maintain Structure** - Keep existing organization and formatting
2. **Update Cross-References** - Fix links when moving or renaming files
3. **Version Information** - Note version for significant changes
4. **Review Process** - Follow same review as code changes

### Documentation Review Checklist
- [ ] Content is accurate and up-to-date
- [ ] Formatting is consistent with project standards
- [ ] Cross-references are correct and working
- [ ] Examples are tested and functional
- [ ] Language is clear and accessible
- [ ] Structure is logical and easy to follow
- [ ] Added to DOCUMENTATION_INDEX.md

---

## Getting Help

### Documentation Issues
- **Missing Information** - Open issue requesting additional documentation
- **Outdated Content** - Report outdated or incorrect information
- **Formatting Issues** - Report formatting or structure problems
- **Accessibility** - Report accessibility or clarity issues

### Contributing Documentation
- **Pull Requests** - Submit documentation improvements via PRs
- **Issue Discussion** - Discuss major documentation changes via issues
- **Community Input** - Seek community feedback on improvements

---

## Document Statistics

**Last Updated:** 2025-11-11

| Category | Document Count |
|----------|----------------|
| Core Documentation | 3 files |
| Container Documentation | 7 files |
| HDLForge Documentation | 9 files |
| Example Documentation | 2 files |
| **Total** | **26+ markdown files** |

---

This documentation index serves as a comprehensive guide to all Fabrinetes documentation, helping users find the information they need quickly and efficiently. All documentation follows a **"big picture → details"** structure for optimal learning and reference.

---

## Document History

**Last Updated:** Commit `b1dfa6d6a9b4f65bba02265a196e9590650b6585` - Update documentation index to reflect new structure (2025-11-11)
