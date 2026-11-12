# DFT organizer

This is a command-line tool to manage the data from DFT (density functional theory) calculations using [CRYSTAL](https://www.crystal.unito.it) and [FLEUR](https://www.flapw.de) engines.

It automates:
- archiving calculation directories with 7z compression
- parsing output files to generate detailed error reports and CSV summaries
- cleaning up original calculation directories after archiving

It also supports unpacking 7z archives and restoring archived calculation directories recursively, with optional AiiDA UUID tracking.


## Installation

Requires Python ≥ 3.9 and `7z` command-line tool.

Install via pip: `pip install .`


## Command-line Interface

### Archive a directory and generate a report

dft-pack --path <directory_path> [--report|--no-report] [--aiida|--no-aiida] [--skip-errors|--no-skip-errors]

- `--path`         Path to the calculation directory
- `--report`       Generate error report and summary (default)
- `--no-report`    Skip report generation
- `--aiida`        Extract UUID from AiiDA directory structure
- `--no-aiida`     Do not extract UUID
- `--skip-errors`  Skip calculations with errors to create summary table

Creates:

- `<directory_name>.7z`
- `report_crystal_<timestamp>.txt` and/or `report_fleur_<timestamp>.txt`
- `summary_<timestamp>.csv`


### Unpack an archive and generate reports

dft-unpack --path <archive_or_directory_path> [--report|--no-report] [--aiida|--no-aiida] [--skip-errors|--no-skip-errors]

- `--path`         Path to a .7z archive or directory with archives
- `--report`       Generate summary and error reports after extraction (default)
- `--no-report`    Skip report generation
- `--aiida`        Extract UUID from AiiDA directory structure
- `--no-aiida`     Do not extract UUID
- `--skip-errors`  Skip calculations with errors to create summary table

Creates under parent directory:
- `summary_<timestamp>.csv`
- `report_crystal_<timestamp>.txt`
- `report_fleur_<timestamp>.txt`

Example:
`dft-report --path /data/aiida_data --aiida --skip-errors`


### Generate reports without archiving

dft-report --path <directory_path> [--aiida|--no-aiida] [--skip-errors|--no-skip-errors] [--calc-type TYPE] [--no-strict-filter]

- `--path`         Root directory containing calculations
- `--aiida`        Extract UUID from AiiDA directory structure
- `--no-aiida`     Do not extract UUID
- `--skip-errors`  Skip calculations with errors to create summary table
- `--calc-type`    Filter by calculation type: `scf`, `optimise`, `phonon`, `transport`, `elastic`, `electron`, `properties`, or `all` (default). For CRYSTAL, `phonon`/`transport`/`elastic`/`electron` are detected from sibling files (`SEEBECK.DAT`, `PHONON.DAT`/`FREQ.DAT`, `ELASTIC.DAT`, `BAND.DAT`/`DOSS.DAT`) or keywords in the OUTPUT file.
- `--no-strict-filter`  Disable the strict CSV filter (by default, rows with `exit_status != 0` or no `chemical_formula` are dropped from the CSV; the JSON keeps everything).

Creates under parent directory:
- `summary_<timestamp>.csv`
- `report_crystal_<timestamp>.txt`
- `report_fleur_<timestamp>.txt`


### Generate reports from AiiDA database (no archiving)

dft-report-aiida [--label LABEL] [--from-date YYYY-MM-DD] [--to-date YYYY-MM-DD] [--calc-type TYPE] [--skip-errors] [--engine ENGINE] [--max-duration HOURS] [--skip-displacement] [--no-strict-filter] [--provider PROVIDER] [--machine-type PLAN] [--output-dir DIR]

- `--label`             Filter by calculation label (exact match)
- `--from-date`         Only include calculations created on or after this date
- `--to-date`           Only include calculations created on or before this date
- `--calc-type`         Only include calculations of this type, e.g. `phonon`, `transport`, `elastic`, `electron`, `optimise`, `scf`, `struct`, `hform`. Filtering is applied after enrichment (so `scf` rows reclassified to `transport` via `SEEBECK.DAT` are kept by `--calc-type transport`).
- `--skip-errors`       Skip calculations with exit_status != 0
- `--engine`            Only include calculations of this engine (`crystal` or `fleur`). Use `crystal` for crystal-only reports (much faster — skips FLEUR enrichment).
- `--max-duration`      Drop calculations with wall-clock duration above this threshold in hours (filters out stalled calcs with inflated `mtime - ctime`). Default 200h; set to 0 to disable.
- `--skip-displacement` Debug/preview only. Skip the slow pg8000 FLEUR displacement enrichment (`calc_type` stays `scf` instead of `optimise`). Off by default; production keeps it on. A follow-up will make enrichment fast enough to always run.
- `--no-strict-filter`  Disable the strict CSV filter (by default, rows with `exit_status != 0` or no `chemical_formula` are dropped from the CSV; the JSON keeps everything).
- `--provider`          Override cloud provider for cost calculation: `hetzner` or `vultr` (default: auto-detect from the AiiDA computer name, or read from `/etc/yascheduler/yascheduler.conf`).
- `--machine-type`      Override machine type (cloud plan, e.g. `vbm-24c-256gb-amd`) for cost calculation. Default: read from `/etc/yascheduler/yascheduler.conf`.
- `--output-dir`        Directory to save reports (default `/tmp`)

Creates:
- `summary_<timestamp>.csv`
- `summary_<timestamp>.json`
- `report_crystal_<timestamp>.txt` / `report_fleur_<timestamp>.txt` (only if errors found)


### FLEUR reports from AiiDA database

FLEUR calculations in the AiiDA database include SCF runs (`scf: fleur run N`) and Seebeck-DOS runs (`<material> : Seebeck coefficient calculation from DOS (Fleur) - DOS`). Input-generator calculations (`fleur.inpgen`) are automatically excluded — they have no results.

By default, FLEUR displacement enrichment runs and reclassifies `scf` → `optimise` for geometry-optimization runs (it compares initial and final structures via a `pg8000` direct-DB query). `--skip-displacement` is a debug/preview shortcut that skips this slow query — all FLEUR rows then stay `scf`. Production reports keep displacement on; a follow-up PR will migrate the query to QueryBuilder so it is fast enough to always run.

**All FLEUR calculations (production default, with displacement):**
```bash
dft-report-aiida --engine fleur --skip-errors --from-date 2026-04-01 --output-dir ./reports/aiida_db
```

**Only Seebeck / transport calculations:**
```bash
dft-report-aiida --engine fleur --skip-errors --calc-type transport --from-date 2026-04-30 --to-date 2026-06-26 --output-dir ./reports/aiida_db
```

**Only SCF calculations (with bandgap, total energy, magnetic moment):**
```bash
dft-report-aiida --engine fleur --skip-errors --calc-type scf --from-date 2026-04-01 --output-dir ./reports/aiida_db
```

**Debug/preview — skip slow displacement (all FLEUR rows stay `scf`):**
```bash
dft-report-aiida --engine fleur --skip-errors --skip-displacement --from-date 2026-04-01 --output-dir ./reports/aiida_db
```

**Include stalled calcs (no duration filter):**
```bash
dft-report-aiida --engine fleur --skip-errors --max-duration 0 --from-date 2026-04-01 --output-dir ./reports/aiida_db
```

FLEUR Seebeck-DOS calculations have labels like `AlAs : Seebeck coefficient calculation from DOS (Fleur) - DOS` and were run between 2026-04-30 and 2026-06-26 (92 calculations). The `output_parameters` port provides `bandgap`, `total_energy`, `fermi_energy`, `magnetic_moment`, and `n_iterations` for all successful `fleur.fleur` calcs. Seebeck data (`seebeck_coefficient_uvk`, `mu_ev`, `temperature_k`) is populated only for Seebeck-DOS calcs.


### CRYSTAL reports from AiiDA database

CRYSTAL calculations in the AiiDA database include SCF runs, geometry optimizations (`<material>: Geometry optimization [N]`), phonon calculations (`<material>: Phonon frequencies [N]`), elastic constants, and transport/Seebeck runs. The `--engine crystal` flag queries only CRYSTAL CalcJobNodes — no `pg8000` displacement is needed, so `--skip-displacement` is not required.

**All CRYSTAL calculations (fast):**
```bash
dft-report-aiida --engine crystal --skip-errors --from-date 2026-06-01 --output-dir ./reports/aiida_db
```

**Only phonon calculations (with frequencies parsed from OUTPUT):**
```bash
dft-report-aiida --engine crystal --skip-errors --calc-type phonon --from-date 2026-06-01 --output-dir ./reports/aiida_db
```

**Only transport / Seebeck calculations:**
```bash
dft-report-aiida --engine crystal --skip-errors --calc-type transport --from-date 2026-06-01 --output-dir ./reports/aiida_db
```

**Only geometry optimization:**
```bash
dft-report-aiida --engine crystal --skip-errors --calc-type optimise --from-date 2026-06-01 --output-dir ./reports/aiida_db
```

**All CRYSTAL including stalled calcs (no duration filter):**
```bash
dft-report-aiida --engine crystal --skip-errors --max-duration 0 --from-date 2025-10-01 --output-dir ./reports/aiida_db
```

The `--max-duration 200` (default) filters out stalled phonon calculations with inflated `mtime - ctime` (some show durations of 6000+ hours / 250+ days, which is a measurement artifact, not real compute time). Set `--max-duration 0` to include them.

Phonon frequencies are parsed from the `MODES ... FREQUENCIES (CM**-1) (THZ)` block in the retrieved `OUTPUT` file. Seebeck data is parsed from `SEEBECK.DAT` in the retrieved repository. Silent-failed transport calcs (`exit_status=0` but `SEEBECK.DAT` contains only a header, no data) are automatically dropped from the summary.


## Python API

### Archive a directory and generate an error report, skip errors

```
from pathlib import Path
from dft_organizer.core import archive_and_save

archive_and_save(
	Path("./my_calc_dir"),
	engine="crystal",
	make_report=True,
	aiida=True,
	skip_errors=True
)
```

### Restore archived .7z files and generate reports, without errors omission

```
from pathlib import Path
from dft_organizer.core import restore_archives_iterative

restore_archives_iterative(
	Path("./archive_dir.7z"),
	engine="crystal",
	generate_reports=True,
	aiida=True,
	skip_errors=False
)
```

### Generate summary for all calculations, skip errors

```
from dft_organizer.core import generate_reports_only
from pathlib import Path

generate_reports_only(Path("/data/aiida"), aiida=True, skip_errors=True)

```


## Example Report Command by AIIDA UUID

Generate report for a specific calculation UUID:

```
dft-pack report \
--path aiida_playground_data \
--uuid 0ea8a6be-7199-4c3e-9263-fae76e8d081e \
--engine crystal
```

Output files:
- `summary_uuid_<uuid>_<timestamp>.csv`
- `errors_uuid_<uuid>_<timestamp>.txt`


## CSV Summary Fields

- `total_energy`        Total energy in eV (from CRYSTAL `energy`; for FLEUR, from `output_parameters.energy`).
- `energy_hartree`      Total energy converted to Hartree (`total_energy / 27.2114`).
- `bandgap`             Band gap value in eV. For CRYSTAL, from the last conduction entry; for FLEUR, from `output_parameters` (AiiDA-DB mode).
- `duration`            Calculation wall-clock time in hours (if reported by CRYSTAL; for FLEUR/AiiDA-DB, computed as `mtime - ctime`).
- `a`, `b`, `c`         Lattice parameters in Å for the final structure.
- `alpha`, `beta`, `gamma`  Lattice angles in degrees for the final structure.
- `chemical_formula`    Reduced chemical formula of the final structure (from ASE).
- `sum_sq_disp`         Sum of squared atomic displacements between first and last structure.
- `rmsd_disp`           Root-mean-square displacement between first and last structure.
- `output_path`         Full path to the main OUTPUT file for this calculation.
- `uuid`                Calculation UUID (only in AiiDA mode, extracted from directory layout).
- `calc_type`           Calculation type: `scf`, `optimise`, `phonon`, `transport`, `electron`, `elastic`, `struct`, `hform`. In AiiDA-DB mode, `scf` rows whose retrieved repository contains `SEEBECK.DAT` are reclassified as `transport`.
- `has_phonons`         True when CRYSTAL phonon frequencies were parsed (AiiDA-DB mode, `calc_type == 'phonon'`).
- `phonon_freq_min`     Minimum phonon frequency in THz across all q-points.
- `phonon_freq_max`     Maximum phonon frequency in THz across all q-points.
- `phonon_n_imag`       Number of imaginary (unstable) phonon modes (THz < -1e-3).
- `phonon_modes_count`  Number of modes at the first q-point.
- `fermi_energy`        Fermi energy in eV. For FLEUR (AiiDA-DB mode), converted from Hartree (`*27.2114`).
- `magnetic_moment`     Magnetic moment in μB. For FLEUR (AiiDA-DB mode), computed from `spin_dependent_charge_total` (difference between spin-up and spin-down charges).
- `n_iterations`        Number of SCF iterations. For FLEUR (AiiDA-DB mode), from `output_parameters.number_of_iterations_total`.
- `seebeck_coefficient_uvk`  Average Seebeck coefficient in µV/K. For CRYSTAL, parsed from `SEEBECK.DAT` (transport calcs); for FLEUR, from `FleurDOSLocalWorkChain` `output_seebeck` (already in µV/K).
- `mu_ev`               Chemical potential. For CRYSTAL, in Hartree (from `SEEBECK.DAT`); for FLEUR, in eV. Note: units differ between engines.
- `temperature_k`       Temperature in Kelvin at which Seebeck was computed.
- `cloud_rate`          Cloud hourly rate used for cost calculation (AiiDA-DB mode). `None` when the provider/plan is unknown or cross-provider mismatched.
- `cost`                Estimated cost = `cloud_rate * duration`. Omitted from the CSV when no rate can be determined.
- `currency`            Currency of `cloud_rate`/`cost`: `EUR` (Hetzner) or `USD` (Vultr).


## License

MIT

&copy; [Alina Zhidkovskaya](https://orcid.org/0009-0003-9305-0030) and [Evgeny Blokhin](https://orcid.org/0000-0002-5333-3947), Materials Platform for Data Science OÜ
