# URLLC-CBG Simulation Analysis

## Scope and interpretation

This report summarises the existing simulation outputs. It does not run or modify experiments. The decoder-SNR results describe this stochastic surrogate model and are not calibrated 5G NR BLER or physical-layer results.

## Baseline

| n | mean_preempted_positions | std_preempted_positions | mean_preemption_fraction | mean_affected_cb_count | std_affected_cb_count | mean_affected_cbg_count | std_affected_cbg_count | mean_failed_cbg_count | std_failed_cbg_count | mean_retransmission_positions | mean_retransmission_overhead | std_retransmission_overhead | mean_embb_delivery_efficiency | std_embb_delivery_efficiency | runs_with_failure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0 |

## RQ1 — URLLC traffic level

| traffic_level | n | mean_preempted_positions | std_preempted_positions | mean_preemption_fraction | mean_affected_cb_count | std_affected_cb_count | mean_affected_cbg_count | std_affected_cbg_count | mean_failed_cbg_count | std_failed_cbg_count | mean_retransmission_positions | mean_retransmission_overhead | std_retransmission_overhead | mean_embb_delivery_efficiency | std_embb_delivery_efficiency | mean_delivered_embb_positions | std_delivered_embb_positions | mean_embb_delivery_rate_per_slot | std_embb_delivery_rate_per_slot | runs_with_failure | failure_run_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no_preemption | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 288.0000 | 0.0000 | 14.4000 | 0.0000 | 0 | 0.0000 |
| low | 30 | 6.2000 | 6.1667 | 0.0215 | 3.7667 | 2.8610 | 2.5000 | 1.7568 | 0.1667 | 0.4611 | 24.0000 | 0.0833 | 0.2306 | 0.9500 | 0.1324 | 276.0000 | 33.2016 | 13.8000 | 1.6601 | 4 | 0.1333 |
| medium | 30 | 21.4667 | 11.8634 | 0.0745 | 6.8333 | 1.7237 | 3.7333 | 0.5833 | 0.3000 | 0.5350 | 43.2000 | 0.1500 | 0.2675 | 0.9056 | 0.1619 | 266.4000 | 38.5188 | 13.3200 | 1.9259 | 8 | 0.2667 |
| high | 30 | 57.0667 | 17.9711 | 0.1981 | 8.0000 | 0.0000 | 4.0000 | 0.0000 | 0.5000 | 0.7311 | 100.8000 | 0.3500 | 0.3862 | 0.7962 | 0.2051 | 252.0000 | 52.6380 | 12.6000 | 2.6319 | 11 | 0.3667 |

## RQ2 — Preemption pattern (descriptive results)

| preemption_pattern | n | mean_preempted_positions | std_preempted_positions | mean_preemption_fraction | mean_affected_cb_count | std_affected_cb_count | mean_affected_cbg_count | std_affected_cbg_count | mean_failed_cbg_count | std_failed_cbg_count | mean_retransmission_positions | mean_retransmission_overhead | std_retransmission_overhead | mean_embb_delivery_efficiency | std_embb_delivery_efficiency | mean_delivered_embb_positions | std_delivered_embb_positions | mean_embb_delivery_rate_per_slot | std_embb_delivery_rate_per_slot | runs_with_failure | failure_run_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no_preemption | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 288.0000 | 0.0000 | 14.4000 | 0.0000 | 0 | 0.0000 |
| concentrated | 30 | 58.0000 | 0.0000 | 0.2014 | 8.0000 | 0.0000 | 4.0000 | 0.0000 | 0.5000 | 0.6297 | 108.0000 | 0.3750 | 0.3641 | 0.7738 | 0.1893 | 252.0000 | 45.3401 | 12.6000 | 2.2670 | 13 | 0.4333 |
| distributed | 30 | 58.0000 | 0.0000 | 0.2014 | 8.0000 | 0.0000 | 4.0000 | 0.0000 | 0.4333 | 0.6261 | 103.2000 | 0.3583 | 0.3695 | 0.7849 | 0.1926 | 256.8000 | 45.0765 | 12.8400 | 2.2538 | 11 | 0.3667 |
| random | 30 | 58.0000 | 0.0000 | 0.2014 | 8.0000 | 0.0000 | 4.0000 | 0.0000 | 0.4333 | 0.6261 | 96.0000 | 0.3333 | 0.3616 | 0.7979 | 0.1906 | 256.8000 | 45.0765 | 12.8400 | 2.2538 | 11 | 0.3667 |

## RQ3 — Number of CBGs

| cbg_count | n | mean_preempted_positions | std_preempted_positions | mean_preemption_fraction | mean_affected_cb_count | std_affected_cb_count | mean_affected_cbg_count | std_affected_cbg_count | mean_failed_cbg_count | std_failed_cbg_count | mean_retransmission_positions | mean_retransmission_overhead | std_retransmission_overhead | mean_embb_delivery_efficiency | std_embb_delivery_efficiency | mean_delivered_embb_positions | std_delivered_embb_positions | mean_embb_delivery_rate_per_slot | std_embb_delivery_rate_per_slot | runs_with_failure | failure_run_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 60 | 29.0000 | 29.2447 | 0.1007 | 4.0000 | 4.0338 | 1.0000 | 1.0084 | 0.0833 | 0.3340 | 45.6000 | 0.1583 | 0.4064 | 0.9233 | 0.1793 | 276.0000 | 48.1016 | 13.8000 | 2.4051 | 4 | 0.0667 |
| 4 | 60 | 29.0000 | 29.2447 | 0.1007 | 4.0000 | 4.0338 | 2.0000 | 2.0169 | 0.2167 | 0.4903 | 48.0000 | 0.1667 | 0.3042 | 0.8990 | 0.1680 | 272.4000 | 35.3017 | 13.6200 | 1.7651 | 11 | 0.1833 |
| 8 | 60 | 29.0000 | 29.2447 | 0.1007 | 4.0000 | 4.0338 | 4.0000 | 4.0338 | 0.4500 | 0.6746 | 46.8000 | 0.1625 | 0.2113 | 0.8853 | 0.1416 | 271.8000 | 24.2856 | 13.5900 | 1.2143 | 21 | 0.3500 |

## Scheduling realism experiment

This section summarizes the separate scheduling experiment by traffic level, policy, and metric. Confidence intervals use a normal approximation (mean ± 1.96 × sample SD / √n); they are descriptive, not hypothesis tests.

| traffic_level | policy | metric | n | mean | std_dev | ci95_low | ci95_high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| low | aggregate_demand | event_success_rate | 30 | 0.9789 | 0.0590 | 0.9578 | 1.0000 |
| low | aggregate_demand | deadline_miss_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| low | aggregate_demand | capacity_rejection_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| low | aggregate_demand | immediate_rejection_rate | 30 | 0.0211 | 0.0590 | -0.0000 | 0.0422 |
| low | aggregate_demand | unresolved_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| low | aggregate_demand | resource_utilization | 30 | 0.0297 | 0.0143 | 0.0246 | 0.0348 |
| low | deadline_aware_edf | event_success_rate | 30 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| low | deadline_aware_edf | deadline_miss_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| low | deadline_aware_edf | capacity_rejection_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| low | deadline_aware_edf | immediate_rejection_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| low | deadline_aware_edf | unresolved_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| low | deadline_aware_edf | resource_utilization | 30 | 0.0307 | 0.0150 | 0.0254 | 0.0361 |
| medium | aggregate_demand | event_success_rate | 30 | 0.9316 | 0.0510 | 0.9133 | 0.9499 |
| medium | aggregate_demand | deadline_miss_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| medium | aggregate_demand | capacity_rejection_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| medium | aggregate_demand | immediate_rejection_rate | 30 | 0.0684 | 0.0510 | 0.0501 | 0.0867 |
| medium | aggregate_demand | unresolved_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| medium | aggregate_demand | resource_utilization | 30 | 0.1177 | 0.0246 | 0.1089 | 0.1265 |
| medium | deadline_aware_edf | event_success_rate | 30 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| medium | deadline_aware_edf | deadline_miss_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| medium | deadline_aware_edf | capacity_rejection_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| medium | deadline_aware_edf | immediate_rejection_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| medium | deadline_aware_edf | unresolved_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| medium | deadline_aware_edf | resource_utilization | 30 | 0.1282 | 0.0296 | 0.1176 | 0.1388 |
| high | aggregate_demand | event_success_rate | 30 | 0.8412 | 0.0496 | 0.8234 | 0.8589 |
| high | aggregate_demand | deadline_miss_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| high | aggregate_demand | capacity_rejection_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| high | aggregate_demand | immediate_rejection_rate | 30 | 0.1588 | 0.0496 | 0.1411 | 0.1766 |
| high | aggregate_demand | unresolved_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| high | aggregate_demand | resource_utilization | 30 | 0.2589 | 0.0405 | 0.2444 | 0.2733 |
| high | deadline_aware_edf | event_success_rate | 30 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| high | deadline_aware_edf | deadline_miss_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| high | deadline_aware_edf | capacity_rejection_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| high | deadline_aware_edf | immediate_rejection_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| high | deadline_aware_edf | unresolved_rate | 30 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| high | deadline_aware_edf | resource_utilization | 30 | 0.3174 | 0.0504 | 0.2994 | 0.3354 |

## Decoder-SNR sensitivity

| snr_db | preemption_pattern | n | mean_overhead | std_overhead | median_overhead | min_overhead | max_overhead | mean_ci95_low | mean_ci95_high | mean_failed_cbg_count | runs_with_failure | mean_delivery_efficiency | mean_delivered_embb_positions | mean_embb_delivery_rate_per_slot |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6.0000 | concentrated | 200 | 1.5212 | 0.3977 | 1.5000 | 0.5000 | 2.0000 | 1.4675 | 1.5750 | 2.6400 | 200 | 0.4082 | 97.9200 | 4.8960 |
| 6.0000 | distributed | 200 | 1.5212 | 0.4078 | 1.5000 | 0.5000 | 2.0000 | 1.4638 | 1.5762 | 2.6650 | 200 | 0.4088 | 96.1200 | 4.8060 |
| 6.0000 | random | 200 | 1.5188 | 0.3898 | 1.5000 | 0.5000 | 2.0000 | 1.4638 | 1.5725 | 2.6350 | 199 | 0.4082 | 98.2800 | 4.9140 |
| 10.0000 | concentrated | 200 | 0.2700 | 0.3174 | 0.2500 | 0.0000 | 1.5000 | 0.2275 | 0.3150 | 0.2900 | 52 | 0.8302 | 267.1200 | 13.3560 |
| 10.0000 | distributed | 200 | 0.2825 | 0.3261 | 0.2500 | 0.0000 | 1.5000 | 0.2375 | 0.3287 | 0.2850 | 51 | 0.8242 | 267.4800 | 13.3740 |
| 10.0000 | random | 200 | 0.2825 | 0.3328 | 0.2500 | 0.0000 | 1.5000 | 0.2375 | 0.3300 | 0.2900 | 51 | 0.8250 | 267.1200 | 13.3560 |
| 14.0000 | concentrated | 200 | 0.0088 | 0.0524 | 0.0000 | 0.0000 | 0.5000 | 0.0025 | 0.0163 | 0.0050 | 1 | 0.9933 | 287.6400 | 14.3820 |
| 14.0000 | distributed | 200 | 0.0100 | 0.0551 | 0.0000 | 0.0000 | 0.5000 | 0.0037 | 0.0187 | 0.0050 | 1 | 0.9923 | 287.6400 | 14.3820 |
| 14.0000 | random | 200 | 0.0112 | 0.0629 | 0.0000 | 0.0000 | 0.5000 | 0.0037 | 0.0200 | 0.0050 | 1 | 0.9917 | 287.6400 | 14.3820 |

## Paired pattern comparisons

Differences are pattern A minus pattern B. Positive values indicate greater overhead for pattern A. Wilcoxon tests are paired by seed; Holm correction is applied to the three pairwise comparisons within each SNR condition. Confidence intervals use a 20,000-replicate percentile bootstrap.

| snr_db | pattern_a | pattern_b | contrast | n_pairs | mean_difference | ci95_low | ci95_high | p_value | p_holm | significant_holm_0_05 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6.0000 | concentrated | distributed | concentrated - distributed | 200 | 0.0000 | -0.0187 | 0.0200 | 0.8029 | 1.0000 | False |
| 6.0000 | concentrated | random | concentrated - random | 200 | 0.0025 | -0.0288 | 0.0338 | 0.9031 | 1.0000 | False |
| 6.0000 | distributed | random | distributed - random | 200 | 0.0025 | -0.0275 | 0.0325 | 0.9519 | 1.0000 | False |
| 10.0000 | concentrated | distributed | concentrated - distributed | 200 | -0.0125 | -0.0300 | 0.0050 | 0.1348 | 0.4045 | False |
| 10.0000 | concentrated | random | concentrated - random | 200 | -0.0125 | -0.0375 | 0.0112 | 0.2835 | 0.5671 | False |
| 10.0000 | distributed | random | distributed - random | 200 | 0.0000 | -0.0225 | 0.0225 | 1.0000 | 1.0000 | False |
| 14.0000 | concentrated | distributed | concentrated - distributed | 200 | -0.0013 | -0.0037 | 0.0000 | 0.3173 | 0.9519 | False |
| 14.0000 | concentrated | random | concentrated - random | 200 | -0.0025 | -0.0075 | 0.0000 | 0.3173 | 0.9519 | False |
| 14.0000 | distributed | random | distributed - random | 200 | -0.0013 | -0.0075 | 0.0037 | 0.6547 | 0.9519 | False |

## Pattern-by-SNR interaction

The interaction is the change in the concentrated-versus-comparison pattern difference across adjacent SNR levels. An interval containing zero does not establish equivalence; it means this analysis did not resolve a non-zero interaction.

| contrast | snr_low_db | snr_high_db | n_paired_seeds | difference_at_low_snr | difference_at_high_snr | interaction_change | bootstrap_ci95_low | bootstrap_ci95_high | ci_excludes_zero |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| concentrated - distributed | 6.0000 | 10.0000 | 200 | 0.0000 | -0.0125 | -0.0125 | -0.0387 | 0.0138 | False |
| concentrated - distributed | 10.0000 | 14.0000 | 200 | -0.0125 | -0.0013 | 0.0112 | -0.0063 | 0.0288 | False |
| concentrated - random | 6.0000 | 10.0000 | 200 | 0.0025 | -0.0125 | -0.0150 | -0.0563 | 0.0288 | False |
| concentrated - random | 10.0000 | 14.0000 | 200 | -0.0125 | -0.0025 | 0.0100 | -0.0138 | 0.0350 | False |

## Limitations

The SNR sweep contains only the configured operating points. The decoder is not calibrated against measured or standard-derived NR BLER curves. Bootstrap intervals quantify simulation run-to-run uncertainty, not model misspecification. Retransmission overhead is a model metric, not a complete throughput or latency measurement. 
The eMBB delivery-rate metric is successfully delivered logical eMBB positions per configured simulation slot. It is a model-level proxy, not physical throughput in bits/s or Mbps, because the simulator does not model a complete shared eMBB transmission timeline.

Bootstrap replicates: 20000
Bootstrap RNG seed: 20261012
