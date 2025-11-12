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
│   │   ├── docker-installation.md
│   │   ├── setup-script-guide.md
│   │   ├── testing_guide.md
│   │   ├── container-hdlforge-test.md
│   │   └── github-container-registry.md
│   └── hdlforge-doc/                  # HDLForge build system documentation
│       ├── README.md                  # HDLForge documentation guide
│       ├── HDLForge.md                # Main HDLForge documentation
│       ├── HDLForge-Verilator.md      # Verilator integration
│       ├── HDLForge-Vivado.md         # Vivado integration
│       ├── HDLForge-Architecture.md   # Internal architecture
│       ├── HDLForge-Verilator-Examples.md
│       ├── HDLForge-Vivado-Examples.md
│       └── HDLForge_v2_Migration_Guide.md
├── command/                           # Command documentation
│   ├── README.md
│   ├── build/README.md
│   ├── run/README.md
│   ├── test/README.md
│   └── help/README.md
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
- **[Setup Script Guide](container-doc/setup-script-guide.md)** - Using setup.sh for container and image management
- **[Testing Guide](container-doc/testing_guide.md)** - Comprehensive testing procedures and methodologies
- **[Container Path Management](container-doc/container-path-management.md)** - Understanding the path system

### Container Management
- **[Architecture Documentation](container-doc/architecture.md)** - Container architecture and design
- **[Docker Installation](container-doc/docker-installation.md)** - Docker setup
- **[Setup Script Guide](container-doc/setup-script-guide.md)** - Fine-grained container and image lifecycle management
- **[Container HDLForge Test](container-doc/container-hdlforge-test.md)** - Testing HDLForge in container environments
- **[GitHub Container Registry](container-doc/github-container-registry.md)** - Container registry setup and usage

---

## HDLForge Build System

> **📁 Complete HDLForge Documentation:** [hdlforge-doc/README.md](hdlforge-doc/README.md)

### Quick Links
- **[HDLForge Overview](hdlforge-doc/HDLForge.md)** - Main HDLForge documentation and quick start
- **[Verilator Integration](hdlforge-doc/HDLForge-Verilator.md)** - Verilator simulation guide
- **[Vivado Integration](hdlforge-doc/HDLForge-Vivado.md)** - Vivado FPGA implementation guide
- **[Architecture Details](hdlforge-doc/HDLForge-Architecture.md)** - Internal architecture for developers

### Examples
- **[Verilator Examples](hdlforge-doc/HDLForge-Verilator-Examples.md)** - Complete working examples for Verilator
- **[Vivado Examples](hdlforge-doc/HDLForge-Vivado-Examples.md)** - Complete working examples for Vivado

### Migration
- **[HDLForge v2.0 Migration Guide](hdlforge-doc/HDLForge_v2_Migration_Guide.md)** - Migration guide for HDLForge v2.0

---

## Command Documentation

### Command References
- **[Command Overview](../command/README.md)** - Complete command documentation and reference
- **[Build Command](../command/build/README.md)** - Docker build command documentation
- **[Run Command](../command/run/README.md)** - Docker run command documentation
- **[Test Command](../command/test/README.md)** - Testing command documentation
- **[Help Command](../command/help/README.md)** - Help system documentation

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
3. [Container Path Management](container-doc/container-path-management.md) - Understand the path system
4. [Testing Guide](container-doc/testing_guide.md) - Run your first tests

### 👨‍💻 Developers
**Essential reads:**
- [Architecture Documentation](container-doc/architecture.md) - System design and components
- [Bug Prevention Guide](bug-prevention-guide.md) - Common pitfalls and solutions
- [Command Documentation](../command/README.md) - Command reference

### ⚙️ FPGA/HDL Developers
**HDLForge workflow:**
1. [HDLForge Overview](hdlforge-doc/HDLForge.md) - Build system introduction
2. [Verilator Guide](hdlforge-doc/HDLForge-Verilator.md) - Simulation setup
3. [Vivado Guide](hdlforge-doc/HDLForge-Vivado.md) - FPGA implementation
4. [Examples](hdlforge-doc/HDLForge-Verilator-Examples.md) - Working examples

### 🚀 Advanced Users
**Deep dives:**
- [HDLForge Architecture](hdlforge-doc/HDLForge-Architecture.md) - Internal implementation
- [GitHub Container Registry](container-doc/github-container-registry.md) - Container distribution
- [Container HDLForge Test](container-doc/container-hdlforge-test.md) - Advanced testing

---

## Quick Navigation by Topic

### 🐳 Container Management
| Document | Purpose |
|----------|---------|
| [Architecture](container-doc/architecture.md) | Core container architecture and design |
| [Path Management](container-doc/container-path-management.md) | Two-level path system explained |
| [Docker Installation](container-doc/docker-installation.md) | Docker setup and configuration |
| [Setup Script Guide](container-doc/setup-script-guide.md) | setup.sh for granular container/image control |
| [Container Registry](container-doc/github-container-registry.md) | GHCR setup and usage |

### 🔧 Build System (HDLForge)
| Document | Purpose |
|----------|---------|
| [HDLForge Main](hdlforge-doc/HDLForge.md) | Overview, quick start, architecture |
| [Verilator](hdlforge-doc/HDLForge-Verilator.md) | Simulation with Cocotb/Verilator |
| [Vivado](hdlforge-doc/HDLForge-Vivado.md) | FPGA synthesis and implementation |
| [Architecture](hdlforge-doc/HDLForge-Architecture.md) | Internal implementation details |
| [Examples](hdlforge-doc/README.md#level-3-detailed-examples-370-380-lines-each) | Complete working examples |

### 🧪 Testing & Quality
| Document | Purpose |
|----------|---------|
| [Testing Guide](container-doc/testing_guide.md) | Testing procedures and methodologies |
| [Bug Prevention](bug-prevention-guide.md) | Common issues and prevention |
| [Container HDLForge Test](container-doc/container-hdlforge-test.md) | HDLForge container testing |

### 📚 Commands & Examples
| Document | Purpose |
|----------|---------|
| [Command Reference](../command/README.md) | All commands documented |
| [Examples](../examples/README.md) | Example projects and patterns |

---

## Documentation Standards

### File Organization
- **`doc/`** - Main documentation directory
  - **`container-doc/`** - Container-specific documentation
  - **`hdlforge-doc/`** - HDLForge build system documentation
- **`command/`** - Command-specific documentation with README.md per command
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
1. **Determine Category** - Choose appropriate directory (`doc/`, `doc/container-doc/`, `doc/hdlforge-doc/`, `command/`, `examples/`)
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
| Command Documentation | 5 files |
| Example Documentation | 2 files |
| **Total** | **26+ markdown files** |

---

This documentation index serves as a comprehensive guide to all Fabrinetes documentation, helping users find the information they need quickly and efficiently. All documentation follows a **"big picture → details"** structure for optimal learning and reference.

---

## Document History

**Last Updated:** Commit `b1dfa6d6a9b4f65bba02265a196e9590650b6585` - Update documentation index to reflect new structure (2025-11-11)
