# IP-Generator

IP-Generator is a companion toolset for **UFDE+** (Universal FPGA Design Environment). It generates Verilog IP cores — primarily **Block RAM (BRAM)** and **Phase-Locked Loop (PLL)** — from high-level descriptions, which UFDE+ then instantiates in your design.

> **For most users, only the IP generation features are needed.** The synthesis and verification flow described at the end of this document is optional and intended for developers who want to validate generated IPs against the FDP3P7 FPGA backend.

---

## What It Does

| Generator | Input | Output |
|-----------|-------|--------|
| **BRAM IP** | MIF file (memory initialization) | `test.v` — synthesizable Verilog RAM module |
| **PLL IP** | Divide ratio & gate count | `PLL_<divide>_<gates>.v` — clock multiplier module |
| **Image → MIF** | PNG / JPG / BMP | `*.mif` — GraphicLCD initialization file (128×64) |

The generators are used by UFDE's graphical IP Catalog. You can also run them standalone from the command line.

---

## Project Layout

```
IP-Generator/
│
│  === IP Generation Core ===
│
├── ip_main.py              # Unified CLI entry (bram / pll sub-commands)
├── bram_generator.py       # BRAM generator engine
├── pll_generator.py        # PLL generator engine
├── img2mif.py              # Image → GraphicLCD MIF converter
│
├── templates/              # Jinja2 Verilog templates
│   ├── bram_template.j2
│   └── pll_template.j2
│
├── ip_generator.spec       # PyInstaller spec for ip_generator.exe
├── img2mif.spec            # PyInstaller spec for img2mif.exe
│
│  === Optional: Validation & Synthesis Flow ===
│
├── test_ram.py             # Automated test-bench generator (all BRAM configs)
├── templates_test/         # Test-bench / wrapper / MIF templates
├── scripts/
│   └── preprocess_netlist.ps1
│
├── run_flow.bat            # Full FPGA flow: syn → map → pack → place → route → bit
├── run_all.bat
├── run_sim_quick.bat
├── run_sim_stage.bat
└── run_all_sim_stages.bat
```

> The synthesis flow scripts expect a backend toolchain in a `bin/` directory. See [Optional: Obtaining the Backend Toolchain](#optional-obtaining-the-backend-toolchain) if you need to run physical validation.

---

## Requirements

- **Python** ≥ 3.8
- **PyInstaller** (to build the executables UFDE consumes)
- **jinja2**, **Pillow**

```bash
pip install pyinstaller jinja2 Pillow
```

---

## Building the Executables

UFDE calls two bundled executables. Build them with PyInstaller using the provided `.spec` files:

```bash
# 1. Unified IP generator (BRAM + PLL)
pyinstaller ip_generator.spec

# 2. Image → MIF converter
pyinstaller img2mif.spec
```

After building you will find:

```
dist/
├── ip_generator.exe
└── img2mif.exe
```

### Integration with UFDE

Copy both executables into your `ufde-next` project directory (the exact location depends on how UFDE locates its helper tools; typically alongside the other bundled binaries). UFDE's IP Catalog will then invoke `ip_generator.exe` and `img2mif.exe` transparently when you configure BRAM or PLL instances.

---

## Standalone Usage

You do not need UFDE to use the generators — they work perfectly from the command line.

### BRAM from MIF

```bash
python ip_main.py bram input.mif --output bram.v
```

Supported MIF parameters: `WIDTH=`, `DEPTH=`, `WIDTHA=`, `DEPTHA=`, `WIDTHB=`, `DEPTHB=`, `ADDRESS_RADIX=`, `DATA_RADIX=`. Single-port and dual-port modes are both supported.

### PLL

```bash
# Single configuration
python ip_main.py pll --divide 2 --gates 30 --output PLL_2_30.v

# All combinations (4 divide values × 2 gate counts = 8 files)
python ip_main.py pll --all --output-dir ./generated
```

| Parameter | Values | Description |
|-----------|--------|-------------|
| `divide` | 2, 4, 8, 16 | Clock divide ratio |
| `gates` | 30, 50 | 30 = 30W (DLL primitive), 50 = 50W (DCM primitive) |

### Image → MIF

```bash
# Convert a picture to GraphicLCD MIF (128×64, 8-column vertical strip)
python img2mif.py image.png -o output.mif

# With preview
python img2mif.py image.png -o output.mif -p preview.png

# Invert colours
python img2mif.py image.png -o output.mif --invert

# Built-in test patterns
python img2mif.py -t checker -o checker.mif -p preview.png
```

---

## Supported BRAM Configurations

Based on the 4Kb `RAMB4_Sx` primitive. Up to 16 primitives can be combined in parallel.

### Single-Port (25 configurations)

| Capacity | width × depth |
|----------|---------------|
| 4Kb  | 1×4096, 2×2048, 4×1024, 8×512, 16×256 |
| 8Kb  | 2×4096, 4×2048, 8×1024, 16×512, 32×256 |
| 16Kb | 4×4096, 8×2048, 16×1024, 32×512, 64×256 |
| 32Kb | 8×4096, 16×2048, 32×1024, 64×512, 128×256 |
| 64Kb | 16×4096, 32×2048, 64×1024, 128×512, 256×256 |

### Dual-Port (75 configurations)

Symmetric and asymmetric dual-port are supported; total capacity of Port A must equal Port B. See `_VALID_DUAL_PORT` in `test_ram.py` for the complete list.

---

## Optional: Validation & Backend Synthesis

The following sections are **only for developers** who want to verify generated IPs against the FDP3P7 physical backend or run regression tests.

### Automated Test Generation

```bash
python test_ram.py
```

This creates the full matrix of BRAM configurations under `test/`, each containing:
- `test.mif` — initialization data
- `test.v` — generated BRAM IP
- `top.v` — wrapper module
- `tb_test.sv` — SystemVerilog test-bench
- `top_cons.xml` — pin constraints

### FPGA Synthesis Flow

```bash
# Single configuration
run_flow.bat test\16x1024

# Batch all configurations
run_all.bat test
```

### Simulation

```bash
# RTL only
run_sim_quick.bat test\16x1024

# Post-synthesis stages
run_sim_stage.bat test\16x1024 rtl
run_sim_stage.bat test\16x1024 map
run_sim_stage.bat test\16x1024 pack
run_sim_stage.bat test\16x1024 route
```

---

## Optional: Obtaining the Backend Toolchain

If you run the validation flow, the scripts expect a `bin/` directory containing:

```
bin/
├── yosys.exe          # Synthesis (Yosys open-source project)
├── yosys-abc.exe      # Yosys ABC integration
├── import.exe         # Verilog → XML (FDE-Source)
├── map.exe            # Technology mapping (FDE-Source)
├── pack.exe           # Cluster packing (FDE-Source)
├── place.exe          # Physical placement (FDE-Source)
├── route.exe          # Signal routing (FDE-Source)
└── bitgen.exe         # Bitstream generation (FDE-Source)
```

These binaries are **not** included in this repository. Obtain them in one of two ways:

1. **Build from Yosys + FDE-Source**
   - `yosys.exe` / `yosys-abc.exe` — build or download from the [YosysHQ/yosys](https://github.com/YosysHQ/yosys) project.
   - `import.exe`, `map.exe`, `pack.exe`, `place.exe`, `route.exe`, `bitgen.exe` — build from the `FDE-Source` repository.

2. **Copy from an existing UFDE+ installation**
   - If you have UFDE+ installed, copy the toolchain binaries from its installation directory into `bin/`.

---

## License

MIT License

## Author

[@FrancisCYH](https://github.com/FrancisCYH)
