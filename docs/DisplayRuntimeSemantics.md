# Display Runtime Semantics

This document records the production behavior of the offline Sweet POWER
display after the Stage 39B display refinements.

## Status Header

The `LXP1` and `LXP2` header status is driven by the packet age reported by
`gateway_snapshot_age`.

| Packet age | Header text | Color |
| ---: | --- | --- |
| `< 15s` | `On` | Green |
| `15s..59s` | `Wait (<age>)` | Yellow |
| `>= 60s` | `Off (<age>)` | Red |

The timer in `Wait` and `Off` shows how long no packets have arrived from that
inverter path.

## Value Retention

Displayed inverter values must not disappear during the `Wait` interval.

The display preserves the last valid values for:

- per-inverter `Solar`;
- per-inverter `Grid`;
- per-inverter `Battery`;
- their TOTAL fields;
- the `Export` indicator.

Values are blanked to `--` only when the corresponding inverter path reaches
the transport `Off` state, which currently means no packets for `60s`.

## Source Freshness Versus Packet Arrival

Gateway source-freshness diagnostics are still decoded and published. A packet
can arrive while the Gateway reports a short source/cache gap.

For the offline HMI, packet arrival and visible value blanking are intentionally
separated:

- short source/cache gap: keep last displayed values;
- packet age `15s..59s`: show `Wait`, keep last displayed values;
- packet age `>= 60s`: show `Off`, blank displayed values.

This prevents brief LXP2 source/cache gaps from clearing `Solar`, `Grid`,
`Battery`, and the dependent TOTAL fields while the inverter path is otherwise
alive.

## Verification

The behavior is covered by host-side tests:

- `tools/run_display_derived_values_tests.py`
- `tools/run_display_source_freshness_tests.py`
- `tools/run_display_uart_receiver_tests.py`

Expected checks:

- source/cache stale with packets still arriving does not blank values;
- transport timeout blanks values exactly at the Off threshold;
- header status transitions remain `On` -> `Wait` -> `Off`;
- `Export` follows link-connected state for blanking, not source-freshness.
