# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check the synthetic chiller against its CSV, not the AIF runtime profile.

Run with a Python environment containing usd-core::

    python nv_core/tiers/simready_foundation_tier_aif/tests/validate_ac_chiller_sample.py --self-test

The sample deliberately populates optional and conditional TABULAR fields so
every CSV row is exercised. The in-memory negative tests never modify assets.
"""

import argparse
import csv
import itertools
import json
import math
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom, UsdPhysics, Vt


ROOT = Path(__file__).resolve().parents[4]
TIER = ROOT / "nv_core/tiers/simready_foundation_tier_aif"
CSV = TIER / "standards/equipment-classes/ac-chiller/AC_Chiller.csv"
ASSET = ROOT / "sample_content/aif/Synthetic_AC_Chiller/asset/Synthetic_AC_Chiller.usda"
PREFIX = "aif:spec:"
TYPES = {
    "float": Sdf.ValueTypeNames.Float,
    "int": Sdf.ValueTypeNames.Int,
    "bool": Sdf.ValueTypeNames.Bool,
    "string": Sdf.ValueTypeNames.String,
    "token": Sdf.ValueTypeNames.Token,
    "float_array": Sdf.ValueTypeNames.FloatArray,
    "int_array": Sdf.ValueTypeNames.IntArray,
    "token_array": Sdf.ValueTypeNames.TokenArray,
}


def validate(stage, rows):
    """Return concrete CSV conformance and synthetic-data consistency failures."""
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    root = stage.GetDefaultPrim()
    if not root:
        return ["Stage has no default prim"]
    check(str(root.GetPath()) == "/Synthetic_AC_Chiller", "Unexpected default prim")
    check(UsdGeom.GetStageMetersPerUnit(stage) == 1.0, "Stage must use metres")
    check(UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.z, "Stage must be Z-up")
    check(
        "synthetic" in (root.GetDocumentation() + json.dumps(
            stage.GetRootLayer().customLayerData, default=str)).lower(),
        "Sample must identify its synthetic provenance",
    )
    names = [row["USD Attribute"] for row in rows]
    check(len(names) == len(set(names)) == 66, "CSV must contain 66 unique attributes")
    check(all(row.get("Default Value") == "" for row in rows),
          "This matrix must leave Default Value cells empty")
    actual = {a.GetName() for a in root.GetAttributes() if a.GetName().startswith(PREFIX)}
    check(actual == set(names), "CSV/USD attribute set mismatch: "
          f"missing={sorted(set(names) - actual)}, extra={sorted(actual - set(names))}")
    values = {}
    for row in rows:
        name = row["USD Attribute"]
        attr = root.GetAttribute(name)
        if not attr:
            continue
        kind = row["Type"]
        check(attr.GetTypeName() == TYPES[kind], f"{name}: type mismatch")
        value = attr.Get()
        check(value is not None, f"{name}: missing value")
        check(attr.GetCustomDataByKey("siUnit") == row["SI Unit"], f"{name}: unit mismatch")
        if value is None or attr.GetTypeName() != TYPES[kind]:
            continue
        values[name.removeprefix(PREFIX)] = value
        items = list(value) if kind.endswith("_array") else [value]
        check(bool(items), f"{name}: empty array")
        for item in items:
            if isinstance(item, str):
                check(bool(item.strip()), f"{name}: empty string")
            elif isinstance(item, (int, float)):
                check(math.isfinite(item), f"{name}: nonfinite number")
        if row["Options"] != "Not required":
            options = [s.strip() for s in row["Options"].split("|")]
            if kind == "bool":
                check(str(value).lower() in options, f"{name}: invalid boolean option")
            else:
                check(list(attr.GetMetadata("allowedTokens") or []) == options,
                      f"{name}: allowedTokens mismatch")
                check(all(item in options for item in items), f"{name}: invalid option")
    # Do not run arithmetic on missing or incorrectly typed inputs.
    if len(values) != len(rows):
        return errors

    check(values["performanceModelType"] == "TABULAR", "Sample must exercise TABULAR fields")
    for group, dimensions, lookups in (("Cooling", 6, 7), ("Standby", 1, 1),
                                       ("EvaporatorLiquidPressureDifferential", 2, 1)):
        prefix = "performanceMap" + group
        grids = {n: v for n, v in values.items() if n.startswith(prefix + "Grid")}
        outputs = {n: v for n, v in values.items() if n.startswith(prefix + "Lookup")}
        check(len(grids) == dimensions and len(outputs) == lookups,
              f"{group}: grid/lookup field count mismatch")
        size = math.prod(len(axis) for axis in grids.values())
        for name, axis in grids.items():
            # Vt returns None for an empty slice; a one-point axis is valid.
            samples = list(axis)
            check(len(samples) > 0 and all(a < b for a, b in zip(samples, samples[1:])),
                  f"{name}: grid must be nonempty and strictly increasing")
        for name, lookup in outputs.items():
            check(len(lookup) == size, f"{name}: lookup length must equal grid product {size}")

    for name in ("evaporatorLiquidMassFraction", "cyclingDegradationCoefficient",
                 "referenceCondenserAirEnteringRelativeHumidity"):
        check(0 <= values[name] <= 1, f"{name}: outside [0, 1]")
    check(all(0 <= x <= 1 for x in values[
        "performanceMapCoolingGridCondenserAirEnteringRelativeHumidity"]),
        "Cooling humidity grid: outside [0, 1]")
    check(values["evaporatorFoulingFactor"] >= 0, "Fouling factor must be nonnegative")
    check(values["evaporatorLeavingTemperatureSetpointMinimum"] <=
          values["evaporatorLeavingTemperatureSetpoint"] <=
          values["evaporatorLeavingTemperatureSetpointMaximum"],
          "Temperature setpoint outside operating limits")
    check(values["minimumOperatingEvaporatorLiquidVolumetricFlowRate"] <=
          values["referenceEvaporatorLiquidVolumetricFlowRate"] <=
          values["maximumOperatingEvaporatorLiquidVolumetricFlowRate"],
          "Reference flow outside operating limits")
    power = values["referenceInputPower"]
    cooling = values["referenceNetEvaporatorCapacity"]
    check(power > 0 and cooling > 0, "Reference power and capacity must be positive")
    if power > 0:
        check(math.isclose(cooling / power, values["referenceCOP"], rel_tol=1e-5),
              "Reference COP is inconsistent with capacity/input power")
    check(math.isclose(values["referenceNetCondenserCapacity"], cooling + power, rel_tol=1e-5),
          "Reference condenser capacity is inconsistent with heat balance")
    # These relationships describe this fictional sample, not a general chiller
    # model contract. Its oil-cooler and auxiliary heat terms are explicitly zero.
    check(values["referenceOilCoolerHeat"] == values["referenceAuxiliaryHeat"] == 0,
          "Example reference oil-cooler/auxiliary heat must be zero")
    check(all(x == 0 for name in ("OilCoolerHeat", "AuxiliaryHeat")
              for x in values["performanceMapCoolingLookup" + name]),
          "Example cooling-map oil-cooler/auxiliary heat must be zero")
    for index, (evaporator, input_power, condenser) in enumerate(zip(
            values["performanceMapCoolingLookupNetEvaporatorCapacity"],
            values["performanceMapCoolingLookupInputPower"],
            values["performanceMapCoolingLookupNetCondenserCapacity"])):
        check(math.isclose(condenser, evaporator + input_power, rel_tol=1e-5),
              f"Cooling lookup {index}: inconsistent heat balance")

    grid_order = (
        "EvaporatorLiquidVolumetricFlowRate", "EvaporatorLiquidLeavingTemperature",
        "CondenserAirEnteringDrybulbTemperature", "CondenserAirEnteringRelativeHumidity",
        "AmbientPressure", "CompressorSequenceNumber",
    )
    order = root.GetCustomDataByKey("coolingGridOrder")
    check(isinstance(order, str) and tuple(s.strip() for s in order.split(",")) == grid_order,
          "Example coolingGridOrder metadata mismatch")
    lookup_order = root.GetCustomDataByKey("lookupOrder")
    check(isinstance(lookup_order, str) and lookup_order.startswith(
        "Cartesian product; rightmost grid axis varies fastest."),
        "Example lookupOrder metadata must declare rightmost-axis-fastest ordering")
    axes = [values["performanceMapCoolingGrid" + name] for name in grid_order]
    reference = [values["reference" + name] for name in grid_order]
    matches = [index for index, point in enumerate(itertools.product(*axes))
               if all(math.isclose(a, b, rel_tol=1e-5) for a, b in zip(point, reference))]
    check(len(matches) == 1, "Example reference point must occur exactly once in cooling grid")
    if len(matches) == 1:
        for name in ("InputPower", "NetEvaporatorCapacity", "NetCondenserCapacity"):
            lookup = values["performanceMapCoolingLookup" + name]
            if matches[0] < len(lookup):
                check(math.isclose(lookup[matches[0]], values["reference" + name], rel_tol=1e-5),
                      f"Example reference {name} disagrees with cooling lookup ordering")

    mass = UsdPhysics.MassAPI(root).GetMassAttr().Get()
    check(root.HasAPI(UsdPhysics.MassAPI) and mass is not None and
          math.isclose(mass, values["operatingWeight"], rel_tol=1e-5),
          "Example native MassAPI mass must equal operatingWeight")
    compressors = [p for p in stage.Traverse() if p.GetPath().GetParentPath() ==
                   root.GetPath().AppendChild("Geometry") and p.GetName().startswith("Compressor_")]
    check(len(compressors) == values["numberOfCompressors"] == 2,
          "Compressor geometry/count mismatch")
    check(values["refrigerant"].startswith("R-"), "Refrigerant must begin with R-")
    return errors


def self_test(stage, rows):
    """Prove the main rejection paths with isolated flattened stage copies."""
    cases = [
        ("missing attribute", lambda p: p.RemoveProperty(PREFIX + "nominalVoltage"), "attribute set"),
        ("wrong type", lambda p: replace_type(p), "type mismatch"),
        ("wrong option", lambda p: p.GetAttribute(PREFIX + "condenserType").Set("WATER"), "invalid option"),
        ("wrong unit", lambda p: p.GetAttribute(PREFIX + "nominalVoltage").SetCustomDataByKey("siUnit", "A"), "unit mismatch"),
        ("wrong array length", lambda p: p.GetAttribute(PREFIX + "performanceMapCoolingLookupInputPower").Set(Vt.FloatArray()), "lookup length"),
        ("wrong heat balance", lambda p: p.GetAttribute(PREFIX + "referenceNetCondenserCapacity").Set(1), "heat balance"),
        ("wrong lookup heat balance", change_lookup_balance, "Cooling lookup 0: inconsistent heat balance"),
        ("wrong bounds", lambda p: p.GetAttribute(PREFIX + "evaporatorLiquidMassFraction").Set(2), "outside [0, 1]"),
        ("wrong grid order", lambda p: p.GetAttribute(PREFIX + "performanceMapStandbyGridEnvironmentDryBulbTemperature").Set(Vt.FloatArray([300, 280])), "strictly increasing"),
    ]
    for label, mutate, expected in cases:
        layer = Sdf.Layer.CreateAnonymous("negative.usda")
        layer.TransferContent(stage.Flatten())
        clone = Usd.Stage.Open(layer)
        mutate(clone.GetDefaultPrim())
        errors = validate(clone, rows)
        if not any(expected in error for error in errors):
            raise AssertionError(f"Negative test {label!r} was not rejected: {errors}")
    return len(cases)


def replace_type(prim):
    name = PREFIX + "nominalVoltage"
    prim.RemoveProperty(name)
    prim.CreateAttribute(name, Sdf.ValueTypeNames.String, custom=True).Set("480")


def change_lookup_balance(prim):
    attr = prim.GetAttribute(PREFIX + "performanceMapCoolingLookupNetCondenserCapacity")
    values = list(attr.Get())
    values[0] += 1_000_000
    attr.Set(Vt.FloatArray(values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, default=ASSET)
    parser.add_argument("--csv", type=Path, default=CSV)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    with args.csv.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if "Default Value" not in reader.fieldnames:
            parser.error("CSV is missing the Default Value column")
        rows = list(reader)
    stage = Usd.Stage.Open(str(args.asset))
    if not stage:
        parser.error(f"Could not open {args.asset}")
    errors = validate(stage, rows)
    if errors:
        for error in errors:
            print("FAIL:", error)
        return 1
    print("PASS: 66 CSV attributes; empty defaults, USD types, units, options, TABULAR arrays, bounds, reference/lookup consistency, and native mass")
    if args.self_test:
        print(f"PASS: {self_test(stage, rows)} in-memory negative conformance tests")
    print("Scope: CSV-specific sample conformance; not AIF-Entity profile certification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
