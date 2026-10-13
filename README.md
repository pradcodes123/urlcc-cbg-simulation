# URLLC–eMBB Multiplexing: CBG-Level Preemption and Retransmission Simulation

A reproducible, Python-based simulation study investigating how Ultra-Reliable Low-Latency Communication (URLLC) preemption affects Enhanced Mobile Broadband (eMBB) transmissions, code-block-group (CBG) failures, and retransmission overhead.

The project implements a modular, 5G NR-inspired resource-allocation and retransmission model. It evaluates the effects of URLLC traffic intensity, preemption patterns, and CBG configuration through controlled experiments, repeated simulation trials, automated analysis, and visualisation.

**Project type:** Research methodology / simulation-based quantitative study  
**Language:** Python  
**Primary libraries:** NumPy, Pandas, Matplotlib  
**Testing:** pytest and Python unittest-based tests

---

## Table of Contents

- [1. Overview](#1-overview)
- [2. Research Objectives](#2-research-objectives)
- [3. System Model](#3-system-model)
- [4. Research Questions](#4-research-questions)
- [5. Experimental Design](#5-experimental-design)
- [6. Project Structure](#6-project-structure)
- [7. Installation](#7-installation)
- [8. Running the Experiments](#8-running-the-experiments)
- [9. Analysis and Visualisation](#9-analysis-and-visualisation)
- [10. Metrics](#10-metrics)
- [11. Results Overview](#11-results-overview)
- [12. Reproducibility and Testing](#12-reproducibility-and-testing)
- [13. Assumptions and Limitations](#13-assumptions-and-limitations)
- [14. Future Work](#14-future-work)
- [15. References](#15-references)

---

## 1. Overview

URLLC and eMBB have different service requirements. URLLC prioritises low latency and high reliability, while eMBB prioritises high data rates and efficient resource utilisation.

When both traffic types share radio resources, a URLLC transmission may preempt resources already allocated to an ongoing eMBB transmission. Depending on the location of the interruption and the organisation of the transport block, preemption can affect code blocks and code-block groups, potentially triggering retransmissions.

This project studies that relationship using a controlled simulation.

The model represents the following processing chain:

1. Generate URLLC traffic events.
2. Allocate eMBB resources on a logical resource grid.
3. Schedule URLLC requests and determine which requests can be served.
4. Apply preemption to selected eMBB resource positions.
5. Map affected resource positions to code blocks and CBGs.
6. Evaluate decoding outcomes using the implemented decoding abstraction.
7. Model CBG-level retransmission and HARQ recovery.
8. Calculate performance metrics and aggregate results across repeated runs.

The primary goal is to understand how different traffic and resource configurations influence eMBB retransmission cost and delivery outcomes within the model.

The simulation is designed for experimental control, reproducibility, and methodological transparency rather than complete physical-layer fidelity.

---

## 2. Research Objectives

The project aims to:

- Model URLLC preemption of ongoing eMBB transmissions using a logical time-frequency resource grid.
- Investigate how URLLC traffic intensity affects eMBB resource damage and retransmission overhead.
- Compare concentrated, distributed, and random preemption patterns.
- Examine how CBG configuration influences decoding failures and retransmission consequences.
- Investigate decoder sensitivity under different experimental settings.
- Explore scheduling strategies and URLLC arrival patterns through supplementary experiments.
- Produce reproducible datasets, statistical summaries, and visualisations.
- Validate implementation behaviour using automated tests and explicit model assumptions.

---

## 3. System Model

### 3.1 eMBB resource allocation

The simulation allocates eMBB resources to a transport block represented on a logical resource grid.

Each resource position is represented by its symbol and subcarrier coordinates. The allocation provides the reference set of resources that may be affected by URLLC preemption.

### 3.2 URLLC traffic generation

URLLC traffic is represented as a sequence of events with attributes such as:

- Event identifier
- Arrival time
- Resource demand
- Deadline and scheduling-related information, where applicable

Traffic-generation configurations allow different traffic intensities and arrival patterns to be investigated.

### 3.3 URLLC scheduling and preemption

The simulation supports preemption patterns used in the official experiments and a separate scheduling extension.

Preemption identifies the eMBB resource positions affected by URLLC activity. The resulting set of positions is used to determine which code blocks and CBGs may be affected.

The scheduling extension additionally investigates request admission, deadline-aware scheduling, and resource-capacity constraints.

### 3.4 Code blocks and code-block groups

The eMBB transport block is partitioned into code blocks and CBGs according to the configured mapping.

Affected resource positions are mapped to their corresponding code blocks and CBGs. This enables the simulation to distinguish between the number of resources preempted and the resulting damage at the coding-group level.

### 3.5 Decoding and retransmission

The decoding component evaluates transmission outcomes using the project's controlled decoding abstraction.

The retransmission and HARQ components model recovery of failed CBGs under the implemented assumptions. The simulation records initial failures, recovered CBGs, final failures, retransmission resource usage, and delivery outcomes.

These components represent a simplified model of the relevant mechanisms; they do not implement the complete NR coding, decoding, or HARQ protocol stack.

---

## 4. Research Questions

### RQ1 — Effect of URLLC traffic intensity

**How does URLLC traffic intensity affect eMBB preemption, CBG damage, retransmission overhead, and delivery efficiency?**

The experiment compares a no-preemption baseline with low-, medium-, and high-traffic conditions.

The principal outcomes are the realised preemption fraction, affected code blocks and CBGs, failed CBGs, retransmission overhead, and eMBB delivery efficiency.

### RQ2 — Effect of preemption pattern

**How does the spatial distribution of preempted eMBB resources affect CBG failures and retransmission overhead?**

The experiment compares concentrated, distributed, and random preemption patterns, together with a no-preemption control.

The objective is to examine whether different resource-interruption patterns produce different outcomes under the same general simulation framework.

### RQ3 — Effect of CBG configuration

**How does the number of CBGs affect decoding failures and retransmission consequences?**

The experiment compares different CBG configurations, including 2, 4, and 8 CBGs.

It examines how the number of failed groups, failure occurrence, retransmission overhead, and delivery efficiency change across configurations.

### Supplementary investigations

Additional experiments extend the core study without replacing the official RQ1–RQ3 experiments:

- **Decoder sensitivity:** examines whether observed differences persist under alternative decoding settings.
- **Scheduling realism v2:** compares aggregate-demand admission with deadline-aware scheduling under different URLLC traffic and resource-capacity conditions.
- **URLLC arrival-pattern experiment:** compares Poisson, evenly spaced, and bursty arrivals using a simplified time-aware resource-selection model.

These extensions are reported separately because they investigate different assumptions and experimental questions.

---

## 5. Experimental Design

The study follows a simulation-based quantitative approach.

### 5.1 Baseline

A no-preemption baseline establishes reference behaviour for the eMBB transport block without URLLC-induced resource interruption.

The baseline is used to compare retransmission and delivery metrics against the preempted scenarios.

### 5.2 Controlled experiments

Each official research question varies a defined experimental factor:

| Experiment | Primary independent variable | Main outcomes |
|---|---|---|
| RQ1 | URLLC traffic intensity | Preemption, CBG damage, overhead, delivery efficiency |
| RQ2 | Preemption pattern | Affected CBGs, failure occurrence, overhead, delivery efficiency |
| RQ3 | CBG configuration | Failed CBGs, failure occurrence, overhead, delivery efficiency |

### 5.3 Repeated trials

The experiments use repeated simulation runs and explicit random seeds where applicable.

Results are stored as raw CSV data and aggregated into descriptive summaries. This supports reproducibility, inspection of individual runs, and comparisons across experimental conditions.

### 5.4 Decoder sensitivity

The decoder sensitivity experiment evaluates the implemented decoding abstraction under alternative settings and uses matched seeds for the specified comparisons.

The analysis includes inferential comparisons with multiple-comparison correction. Statistical conclusions are restricted to the comparisons and settings actually evaluated.

### 5.5 Supplementary experiments

The scheduling and arrival-pattern extensions are analysed separately from the official research questions.

In particular, the arrival-pattern experiment uses an explicit simplified mapping from scheduler slots to eMBB symbols. If the number of preempted positions differs across patterns, the resulting comparisons combine changes in preemption quantity and location. Such results should not be interpreted as isolating arrival timing alone.

---

## 6. Project Structure

The repository is organised into configuration, simulation, experiments, analysis, results, and testing components.

```text
urlcc-cbg-simulation/
├── config/
│   └── simulation.py
│
├── src/
│   ├── resource_grid.py
│   ├── embb.py
│   ├── urllc.py
│   ├── scheduler.py
│   ├── preemption.py
│   ├── cbg.py
│   ├── decoder.py
│   ├── channel.py
│   ├── harq.py
│   ├── retransmission.py
│   ├── metrics.py
│   └── simulation.py
│
├── experiments/
│   ├── baseline.py
│   ├── rq1_traffic.py
│   ├── rq2_patterns.py
│   ├── rq3_cbg.py
│   ├── realism_v2.py
│   └── urllc_burst_patterns.py
│
├── analysis/
│   ├── analyze_results.py
│   ├── plots.py
│   ├── grid_views.py
│   └── ...
│
├── tests/
│   ├── test_simulation.py
│   ├── test_channel.py
│   ├── test_harq.py
│   ├── test_scheduler.py
│   ├── test_realism_v2.py
│   ├── test_urllc_burst_patterns.py
│   └── ...
│
├── results/
│   ├── raw/
│   ├── processed/
│   ├── figures/
│   └── urllc_burst_patterns/
│
├── requirements.txt
└── README.md
```

*Note: The tree highlights the principal modules and representative files. Additional experiments, tests, analysis scripts, and result files may exist in the working repository.*

### Main components

| Component | Responsibility |
|---|---|
| `config/` | Simulation and experiment configuration |
| `src/resource_grid.py` | Logical resource-grid representation |
| `src/embb.py` | eMBB transport-block and resource allocation |
| `src/urllc.py` | URLLC traffic-event generation |
| `src/scheduler.py` | URLLC request scheduling |
| `src/preemption.py` | Preemption selection and result representation |
| `src/cbg.py` | Code-block-group mapping |
| `src/decoder.py` | Decoding outcome abstraction |
| `src/channel.py` | Channel-related modelling used by the implemented extensions |
| `src/harq.py` | HARQ recovery logic |
| `src/retransmission.py` | Retransmission modelling |
| `src/metrics.py` | Performance-metric calculation |
| `src/simulation.py` | Integration of the simulation components |
| `experiments/` | Reproducible experiment entry points |
| `analysis/` | Result aggregation, statistical analysis, and plots |
| `tests/` | Automated unit, integration, and regression tests |
| `results/` | Raw data, processed summaries, and generated figures |

---

## 7. Installation

### 7.1 Requirements

- Python 3.12 or a compatible Python version supported by the project dependencies
- NumPy
- Pandas
- Matplotlib
- pytest and any additional packages listed in `requirements.txt`

### 7.2 Clone the repository

```bash
git clone <repository-url>
cd urlcc-cbg-simulation
```

Replace `<repository-url>` with the repository's actual Git URL.

### 7.3 Create a virtual environment

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 7.4 Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run commands from the repository root so that the project modules and relative result paths resolve correctly.

---

## 8. Running the Experiments

Run experiments as Python modules from the repository root.

### 8.1 Official experiments

```bash
python -m experiments.baseline
python -m experiments.rq1_traffic
python -m experiments.rq2_patterns
python -m experiments.rq3_cbg
```

These commands execute the baseline and the three principal research experiments.

### 8.2 Supplementary arrival-pattern experiment

```bash
python -m experiments.urllc_burst_patterns
```

This compares Poisson, evenly spaced, and bursty URLLC arrivals under the experiment's simplified time-aware resource-selection model.

Its results are written separately from the official experiment outputs.

### 8.3 Scheduling extension

The scheduling-realism experiment is implemented in:

```text
experiments/realism_v2.py
```

Run it using the entry point defined by that script and its current command-line interface. Consult the module's `main()` function or its usage documentation for the exact invocation.

**Important:** Do not assume that supplementary experiments share the same configuration, metrics, or output paths as RQ1–RQ3. Check the relevant experiment configuration before rerunning an experiment that overwrites existing raw results.

---

## 9. Analysis and Visualisation

### 9.1 Generate the descriptive figures

```bash
python -m analysis.plots
```

This generates the principal descriptive figures, including:

- Baseline retransmission overhead
- RQ1 affected code blocks and CBGs
- RQ1 failed CBGs
- RQ1 retransmission overhead
- RQ1 eMBB delivery efficiency
- RQ1 realised preemption fraction
- RQ1 preemption-versus-overhead scatter plot
- RQ2 affected code blocks and failed CBGs
- RQ2 retransmission overhead and delivery efficiency
- RQ2 failure occurrence
- RQ2 retransmission-overhead ECDF
- RQ2 logical resource-grid comparison
- RQ2 preemption-to-CBG outcome illustration
- RQ3 failed CBGs
- RQ3 retransmission overhead
- RQ3 delivery efficiency
- RQ3 failure occurrence

Figures are saved under:

```text
results/figures/
```

### 9.2 Run the analysis pipeline

```bash
python -m analysis.analyze_results
```

The analysis pipeline reads the configured raw datasets, generates processed summaries and statistical comparisons, and produces the main analysis report.

The exact outputs depend on the current analysis configuration. Check the script's configured input and output paths before running it over an existing results directory.

### 9.3 Inspect the results

The main results directories are:

```text
results/
├── raw/
├── processed/
├── figures/
└── urllc_burst_patterns/
    ├── raw/
    └── processed/
```

Raw CSV files contain run-level observations. Processed CSV files contain aggregated summaries and other derived outputs. Figures provide visual summaries of the experimental findings.

Raw observations should be retained when reporting means, standard deviations, failure probabilities, or statistical comparisons.

---

## 10. Metrics

The simulation records metrics at several stages of the preemption, decoding, and retransmission process.

### 10.1 Preemption metrics

**Preempted positions**

The number of eMBB resource positions selected for preemption.

**Total eMBB positions**

The number of resource positions in the original eMBB allocation.

**Preemption fraction**

\[
f_{\mathrm{preempt}}
=
\frac{N_{\mathrm{preempted}}}
{N_{\mathrm{eMBB}}}
\]

This measures the fraction of the original eMBB allocation that was preempted.

### 10.2 CBG damage and failure metrics

- `affected_cb_count`: number of distinct affected code blocks.
- `affected_cbg_count`: number of distinct affected CBGs.
- `initial_failed_cbg_count`: number of CBGs that fail initial decoding.
- `failed_cbg_count`: number of CBGs still failing after the modelled recovery process.
- `initial_cbg_failure_rate`: fraction of CBGs failing initial decoding.
- `residual_bler`: fraction of CBGs that remain failed after recovery.

Under the implemented metric definition:

\[
\mathrm{Residual\ BLER}
=
\frac{N_{\mathrm{final\ failed\ CBG}}}
{N_{\mathrm{CBG}}}
\]

This is an abstraction-level residual failure metric, not a validated NR physical-layer BLER measurement.

### 10.3 Retransmission metrics

**Retransmission positions**

The number of resource positions attributed to retransmissions by the implemented model.

**Retransmission overhead**

\[
O_{\mathrm{retx}}
=
\frac{N_{\mathrm{retransmission\ positions}}}
{N_{\mathrm{original\ eMBB\ positions}}}
\]

This ratio is not necessarily bounded by 1.0. It can exceed 1.0 if the model attributes more retransmission positions than the number of positions in the original allocation.

### 10.4 Delivery metrics

The simulation tracks:

- `embb_delivery_efficiency`
- `final_delivery_success_rate`
- `delivered_embb_positions`
- `embb_delivery_rate_per_slot`

These metrics describe different aspects of delivery. They should not be treated as interchangeable: resource-based efficiency, CBG-level success, and delivery rate use different units and denominators.

Refer to the implementation in `src/metrics.py` for the precise calculation of each metric.

### 10.5 Scheduling metrics

The scheduling extensions record measures such as:

- Scheduling success rate
- Deadline-miss rate
- Capacity-rejection rate
- Scheduled resource units

These metrics apply to the scheduling experiments and should be interpreted within their respective models.

---

## 11. Results Overview

The following observations summarise the results obtained from the current experimental datasets. Values are descriptive means or run-level proportions, not universal predictions for deployed 5G NR systems.

### 11.1 RQ1: Traffic intensity

The official RQ1 experiment shows increasing mean retransmission overhead as URLLC traffic intensity rises.

Previously reported means are:

| Condition | Mean retransmission overhead | Mean eMBB delivery efficiency |
|---|---:|---:|
| Baseline | 0.000 | 1.000 |
| Low traffic | 0.083 | 0.950 |
| Medium traffic | 0.150 | 0.906 |
| High traffic | 0.350 | 0.796 |

The results are consistent with the expected mechanism: greater URLLC traffic produces more preemption and, under the implemented model, greater eMBB retransmission cost.

### 11.2 RQ2: Preemption pattern

The previously reported mean retransmission overheads are:

| Pattern | Mean retransmission overhead |
|---|---:|
| Concentrated | 0.375 |
| Distributed | 0.358 |
| Random | 0.333 |

The results suggest that the spatial arrangement of preempted resources can influence retransmission outcomes within the simulation.

The comparison is descriptive. It should not be interpreted as proving that concentrated preemption is universally worse in real NR deployments.

### 11.3 RQ3: CBG configuration

The previously reported mean failed-CBG counts are:

| CBG configuration | Mean failed CBGs | Runs with at least one failed CBG |
|---:|---:|---:|
| 2 CBGs | 0.083 | 6.7% |
| 4 CBGs | 0.217 | 18.3% |
| 8 CBGs | 0.450 | 35.0% |

The failure count and failure occurrence increase across the tested configurations. Retransmission overhead does not necessarily follow the same trend, demonstrating that these metrics capture different aspects of the model's behaviour.

### 11.4 Decoder sensitivity

The decoder sensitivity experiment contains 1,800 raw observations, with 200 matched seeds per pattern/SNR combination across nine summary groups.

The previously reported analysis found no statistically significant differences for the tested comparisons after Holm correction, and the tested SNR-interaction confidence intervals included zero.

These findings indicate that the analysis did not establish statistically significant effects for those comparisons. They do not demonstrate equivalence between configurations or validate the decoder against a complete NR physical layer.

### 11.5 Scheduling extension

The scheduling-realism experiment compares aggregate-demand admission with deadline-aware scheduling under different resource-capacity conditions.

The results explore how scheduling success changes as resources become more constrained. This experiment is a supplementary extension and is not part of the official RQ1–RQ3 analysis.

### 11.6 Arrival-pattern extension

The supplementary arrival-pattern experiment includes 600 runs:

| Arrival pattern | Runs |
|---|---:|
| Poisson | 200 |
| Evenly spaced | 200 |
| Bursty | 200 |

The current results show 100% scheduling success and zero deadline misses across the three patterns. They also show differences in mean preemption count and eMBB metrics.

Because preemption counts differ between patterns, these results do not isolate the effect of arrival timing alone.

### Interpretation

Taken together, the experiments investigate the relationships between URLLC traffic, resource preemption, CBG damage, and retransmission behaviour. The findings apply to the specified simulation assumptions and configurations.

The official research questions should remain distinct from the supplementary scheduling and arrival-pattern experiments when interpreting and reporting the results.

---

## 12. Reproducibility and Testing

Reproducibility is supported by:

- Explicit random seeds where applicable
- Configuration-driven simulation behaviour
- Run-level CSV outputs
- Automated result aggregation
- Deterministic visualisation settings where applicable
- Unit and regression tests

### Run the full test suite

Activate the project virtual environment and run:

```bash
python -m pytest -q
```

The latest recorded test run completed successfully:

```text
271 passed, 1023 subtests passed in 8.57s
```

This is the result of the most recently reported test run. Test counts and timings may change as the repository evolves.

Passing tests establish consistency with the tested implementation contracts. They do not independently establish external physical-layer validity.

---

## 13. Assumptions and Limitations

The simulation deliberately uses a controlled abstraction of selected NR-inspired mechanisms.

### 13.1 Simplified physical layer

The project does not implement a complete NR physical layer, including a full standards-compliant coding and decoding chain, channel estimation, link adaptation, or complete protocol-stack behaviour.

### 13.2 Abstract decoding

Decoding outcomes are determined using the implemented model rather than a validated NR link-level decoder. Consequently, residual failure metrics should not be interpreted as directly measured real-world BLER.

### 13.3 Simplified preemption and resource mapping

The resource grid, preemption selection, and CBG damage mapping follow the project's explicit allocation rules. They do not capture every scheduling and resource-mapping procedure of a deployed NR system.

### 13.4 HARQ abstraction

HARQ recovery is represented under the assumptions implemented in the simulation. The results do not reproduce every timing, signalling, soft-combining, and retransmission detail of the complete NR HARQ process.

### 13.5 Supplementary experiment scope

The scheduling-realism and arrival-pattern experiments use their own experimental assumptions and should not be treated as integrated validation of the official RQ1–RQ3 pipeline.

### 13.6 Statistical interpretation

Most principal results are descriptive comparisons. Inferential conclusions should be restricted to the comparisons for which statistical tests and uncertainty estimates have actually been calculated.

### 13.7 External validity

The project has not established that its numerical results generalise directly to deployed cellular networks. Such validation would require additional modelling, calibration, and comparison with an appropriate reference implementation or independent dataset.

These limitations define the scope of the study rather than invalidate its purpose. The project prioritises controlled experimentation, traceability, and reproducible analysis within a manageable simulation framework.

---

## 14. Future Work

Potential extensions include:

- Integrating a more detailed NR link-level or system-level simulator.
- Validating decoding and retransmission assumptions against independent reference results.
- Refining the relationship between URLLC scheduling time, preemption time, and eMBB resource mapping.
- Conducting matched-preemption experiments that isolate resource-placement effects from total preemption quantity.
- Expanding statistical analysis with effect sizes and confidence intervals for selected comparisons.
- Investigating additional traffic models and resource-allocation configurations.
- Integrating the supplementary scheduling and arrival-pattern extensions into a more unified experimental framework.

These extensions are outside the minimum scope of the current controlled simulation study.

---

## 15. References

The project is motivated by the 5G NR resource-allocation and physical-layer framework specified in 3GPP technical specifications.

Relevant standards include:

1. **3GPP TS 38.211** — NR; Physical channels and modulation.
2. **3GPP TS 38.214** — NR; Physical layer procedures for data.

The simulation is NR-inspired and uses selected concepts from this framework. It should not be described as a complete implementation of either specification.

---

## Acknowledgement of scope

This project was developed as a research-methodology simulation study. The emphasis is on defining measurable research questions, designing controlled experiments, implementing a transparent simulation model, analysing results, testing reproducibility, and documenting limitations.

The contribution is the structured investigation of URLLC preemption and its effects on eMBB CBG-level outcomes within the implemented model—not a claim of complete 5G NR physical-layer fidelity.
