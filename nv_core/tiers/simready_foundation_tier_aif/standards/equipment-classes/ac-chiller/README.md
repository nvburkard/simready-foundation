# AC_Chiller equipment class standardization

[AC_Chiller.csv](AC_Chiller.csv) defines the air-cooled chiller attribute matrix
for standardization in this PR: 66 attributes and 18 columns, including Options.
It is derived from the [AC_Chiller source tab](https://docs.google.com/spreadsheets/d/1_rMBhj-pIEjy6y62ypBr-7KiXfoBq9g4oY5Ult30B8k/edit#gid=1035323646),
retrieved on 2026-10-30, with the normalization rules below.
Source row IDs, aliases, decision IDs, and baseline comparisons retain traceability.

## Column conventions

- Description explains the quantity or purpose; units and enumerated choices have
  their own SI Unit Values and Options columns.
- Options contains semicolon-separated choices, or `Not required` when no closed
  enumeration is imposed. Array choices apply to each element.
- Refrigerant designations remain open strings beginning with `R-`.
- Communication protocol has no physical unit or closed enumeration. The source's
  `mm` unit is corrected to `Not applicable`; cardinality remains under review.
- `chillerType` is restricted to `Air-Cooled` for this class, consistent with
  `condenserType = AIR`; its redundancy with class identity remains under review.
- Required, Conditional, and Optional are the requirement categories submitted
  for standardization. Review status records review state, not prior approval.

## Units and conversion rules

- Absolute temperatures use K: `T[K] = T[°C] + 273.15`.
- Pipe diameter uses m: `length[m] = length[mm] / 1000`.
- Counts, fractions, and power ratios use `1`; identifiers use `Not applicable`.
- IPLV/NPLV retain input-power/cooling-capacity orientation as a dimensionless
  ratio (W/W): divide a source kW/ton value by `3.516853`. This is the reciprocal
  orientation of cooling/input COP; do not silently interchange them.
- Power and cooling capacity use W. For legacy kW aliases, multiply by 1000 only
  after confirming that the measurement boundaries match.
- `soundPowerLevel` remains an A-weighted logarithmic level in dB referenced to
  1 pW, an explicit non-SI exception. A-weighting does not imply sound pressure.
  Do not relabel this quantity as W.

Celsius and millimetres are valid SI units; K and m are the normalization
conventions used here. All Value cells are empty, so this change normalizes
definitions and supplies conversion rules without converting equipment data.

Conversion references: [NIST SP 811 conversion factors](https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8)
and [ISO 5135:2020 acoustic definitions](https://www.iso.org/obp/ui?_escaped_fragment_=iso%3Astd%3Aiso%3A5135%3Aed-3%3Av1%3Aen).

## Implementation scope

This PR standardizes the CSV attribute matrix. Runtime JSON registration,
thermal/electrical mappings, and validator integration are separate work.
Remaining review decisions include class-identity redundancy, protocol
cardinality, mixture conventions, performance-model validation, and mass boundaries.
