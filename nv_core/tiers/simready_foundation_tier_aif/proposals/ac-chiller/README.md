# AC_Chiller equipment class proposal

[AC_Chiller.csv](AC_Chiller.csv) captures the **air-cooled chiller** equipment
class proposal from the [AC_Chiller source tab](https://docs.google.com/spreadsheets/d/1_rMBhj-pIEjy6y62ypBr-7KiXfoBq9g4oY5Ult30B8k/edit#gid=1035323646).
Snapshot retrieved on 2026-10-30: 66 attributes, 17 columns.

The CSV preserves the source row order, headers, empty values, attribute names,
types, units, applicability, aliases, decision IDs, provenance, and review status.
Only unused trailing spreadsheet rows and columns are omitted. This is a proposal
for review, not an approved equipment-class contract or runtime registration.
Existing AIF profiles and equipment-class JSON configurations are unchanged.

## Review decisions carried forward

- `chillerType`: held pending a redundancy decision with class identity and
  `condenserType` (D01).
- `communicationProtocol`: held pending cardinality (D06). The source unit
  is `mm`; it is preserved verbatim and needs correction or confirmation.
- `soundPowerLevel`: held pending the acoustic definition (D07).
- Legacy `referencePower` / `referenceCapacity` aliases use kW, while proposed
  fields use W; approve the measurement boundary before conversion (D02).
- Resolve water/mixture mass-fraction conventions (D03), performance model
  identity and array validation (D04), and operating/shipping mass boundaries (D05).
- Preserve source temperature distinctions: reference temperatures use °C;
  tabular temperature arrays use K. Do not silently normalize units or aliases.

Runtime adoption requires a reviewed JSON class configuration, explicit
thermal/electrical mappings, synchronized class documentation, and validator tests.
The CSV alone does not register a class with the equipment-class loader.
