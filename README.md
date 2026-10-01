# URLLC-CBG Simulation

Simulation study of the impact of URLLC preemption on eMBB
code-block-group (CBG) retransmissions in 5G NR-inspired systems.

## Research Questions

- **RQ1:** How does URLLC traffic intensity affect the number of
  affected code blocks/CBGs and retransmission overhead?
- **RQ2:** How do different spatial preemption patterns affect
  eMBB CBG damage and retransmission overhead?
- **RQ3:** How does the number of configured CBGs affect the impact
  of URLLC preemption?

## Project Structure

```text
urlcc-cbg-simulation/
├── config/          # Simulation configuration
├── src/             # Core simulation modules
├── experiments/     # Baseline and RQ1-RQ3 experiment drivers
├── analysis/        # Descriptive analysis and plotting
├── tests/           # Automated tests
├── results/         # Raw results, processed summaries and figures
├── requirements.txt
└── README.md
