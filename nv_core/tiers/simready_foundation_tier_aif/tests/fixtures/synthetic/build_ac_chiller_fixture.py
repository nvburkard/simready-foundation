# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Build a fictional AC_Chiller CSV example and its USD render scene.

Run with Python and usd-core installed. Values are illustrative, not vendor
ratings or CSV defaults. The CSV is the attribute/type/unit/option authority.
The tabular fixture uses Cartesian-product order, rightmost axis varying fastest.
Render with: usdrecord --camera /Preview/Camera --imageWidth 1600
    sample_content/aif/Synthetic_AC_Chiller/preview.usda <output.png>
"""

import csv
import itertools
import math
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdShade, Vt

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').exists())
TIER = REPO / 'nv_core/tiers/simready_foundation_tier_aif'
DEST = REPO / 'sample_content/aif/Synthetic_AC_Chiller'
ROOT = '/Synthetic_AC_Chiller'


def values():
    data = dict(
        nominalVoltage=480.0, nominalFrequency=60.0, compressorType='SCREW',
        refrigerant='R-134a', hotGasBypassInstalled=False, condenserType='AIR',
        evaporatorLiquidType='WATER', evaporatorLiquidMassFraction=1.0,
        evaporatorFoulingFactor=0.000018, compressorSpeedControlType='CONTINUOUS',
        cyclingDegradationCoefficient=0.1,
        referenceEvaporatorLiquidVolumetricFlowRate=0.012, referenceElevation=0.0,
        referenceEvaporatorLiquidLeavingTemperature=279.15,
        referenceCondenserAirEnteringDrybulbTemperature=308.15,
        referenceCondenserAirEnteringRelativeHumidity=0.5,
        referenceAmbientPressure=101325.0, referenceCompressorSequenceNumber=2,
        referenceInputPower=100000.0, referenceNetEvaporatorCapacity=400000.0,
        referenceNetCondenserCapacity=500000.0,
        referenceCondenserAirVolumetricFlowRate=32.0,
        referenceOilCoolerHeat=0.0, referenceAuxiliaryHeat=0.0,
        referenceOperationState='NORMAL', performanceModelType='TABULAR',
        performanceModelSource='SyntheticExample', performanceModelVersion='1.0.0',
        performanceModelComponent='IllustrativeAirCooledChiller', referenceCOP=4.0,
        evaporatorLeavingTemperatureSetpoint=279.15,
        evaporatorLeavingTemperatureSetpointMaximum=288.15,
        evaporatorLeavingTemperatureSetpointMinimum=277.15,
        maximumOperatingEvaporatorLiquidVolumetricFlowRate=0.016,
        minimumOperatingEvaporatorLiquidVolumetricFlowRate=0.006,
        evaporatorNominalPipeOutsideDiameter=0.1143,
        electricalRatedFullLoadCurrent=150.0,
        electricalMaximumOvercurrentProtection=225.0,
        electricalMinimumCurrentAmpacity=187.5,
        operatingWeight=2400.0, shippingWeight=2100.0, chillerType='Air-Cooled',
        numberOfCompressors=2, iplv=0.2, nplv=0.22,
        communicationProtocol='BACnet_IP', controller='Synthetic Controller 1',
        soundPowerLevel=85.0,
    )
    axes = {
        'EvaporatorLiquidVolumetricFlowRate': [0.008, 0.012],
        'EvaporatorLiquidLeavingTemperature': [279.15, 283.15],
        'CondenserAirEnteringDrybulbTemperature': [298.15, 308.15],
        'CondenserAirEnteringRelativeHumidity': [0.5],
        'AmbientPressure': [101325.0], 'CompressorSequenceNumber': [1, 2],
    }
    for name, axis in axes.items():
        data['performanceMapCoolingGrid' + name] = axis
    lookups = {k: [] for k in (
        'InputPower', 'NetEvaporatorCapacity', 'NetCondenserCapacity',
        'CondenserAirVolumetricFlowRate', 'OilCoolerHeat', 'AuxiliaryHeat', 'OperationState')}
    for flow, leaving, ambient, humidity, pressure, sequence in itertools.product(*axes.values()):
        capacity = 400000 * (flow / 0.012) * (sequence / 2) * (1 + 0.01 * (leaving - 279.15))
        cop = 4 + 0.05 * (308.15 - ambient)
        power = capacity / cop
        for key, value in zip(lookups, (power, capacity, capacity + power, 16.0 * sequence, 0.0, 0.0, 'NORMAL')):
            lookups[key].append(value)
    for key, array in lookups.items():
        data['performanceMapCoolingLookup' + key] = array
    data.update(
        performanceMapStandbyGridEnvironmentDryBulbTemperature=[293.15, 313.15],
        performanceMapStandbyLookupInputPower=[300.0, 500.0],
        performanceMapEvaporatorLiquidPressureDifferentialGridEvaporatorLiquidVolumetricFlowRate=[0.008, 0.012],
        performanceMapEvaporatorLiquidPressureDifferentialGridEvaporatorLiquidLeavingTemperature=[279.15, 283.15],
        performanceMapEvaporatorLiquidPressureDifferentialLookupEvaporatorLiquidDifferentialPressure=[20000.0, 19500.0, 45000.0, 43875.0],
    )
    return data


def stage_at(path, root):
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1.0)
    prim = UsdGeom.Xform.Define(stage, root).GetPrim()
    stage.SetDefaultPrim(prim)
    return stage


def material(stage, path, color, metallic=0.0, roughness=0.45):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + '/Surface')
    shader.CreateIdAttr('UsdPreviewSurface')
    for name, kind, val in [('diffuseColor', Sdf.ValueTypeNames.Color3f, color),
                            ('metallic', Sdf.ValueTypeNames.Float, metallic),
                            ('roughness', Sdf.ValueTypeNames.Float, roughness)]:
        shader.CreateInput(name, kind).Set(val)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
    return mat


def shape(stage, name, kind, position, scale, mat, rotate=None):
    obj = kind.Define(stage, ROOT + '/Geometry/' + name)
    if kind == UsdGeom.Cube:
        obj.CreateSizeAttr(1.0)
    elif kind == UsdGeom.Cylinder:
        obj.CreateRadiusAttr(1.0)
        obj.CreateHeightAttr(1.0)
        obj.CreateAxisAttr('Z')
    obj.AddTranslateOp().Set(Gf.Vec3d(*position))
    if rotate is not None:
        obj.AddRotateXYZOp().Set(Gf.Vec3f(*rotate))
    obj.AddScaleOp().Set(Gf.Vec3f(*scale))
    UsdShade.MaterialBindingAPI.Apply(obj.GetPrim()).Bind(mat)
    return obj


def build():
    layers = DEST / 'asset/layers'
    layers.mkdir(parents=True, exist_ok=True)
    csv_path = TIER / 'standards/equipment-classes/ac-chiller/AC_Chiller.csv'
    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    data = values()
    assert {r['USD Attribute'].split(':')[-1] for r in rows} == set(data)
    types = {'float': Sdf.ValueTypeNames.Float, 'int': Sdf.ValueTypeNames.Int,
             'string': Sdf.ValueTypeNames.String, 'token': Sdf.ValueTypeNames.Token,
             'bool': Sdf.ValueTypeNames.Bool, 'float_array': Sdf.ValueTypeNames.FloatArray,
             'int_array': Sdf.ValueTypeNames.IntArray, 'token_array': Sdf.ValueTypeNames.TokenArray}
    props = stage_at(layers / 'Synthetic_AC_Chiller_Properties.usda', ROOT)
    prim = props.GetDefaultPrim()
    prim.SetDocumentation('Fictional vendor-neutral AC_Chiller. All values are synthetic examples, not manufacturer ratings or CSV defaults.')
    for name, value in {'assetClass': 'AC_Chiller', 'assetDescription': 'Synthetic air-cooled chiller for CSV conformance demonstration'}.items():
        prim.CreateAttribute('aif:core:' + name, Sdf.ValueTypeNames.String).Set(value)
    for row in rows:
        attr = prim.CreateAttribute(row['USD Attribute'], types[row['Type']], custom=True)
        attr.Set(data[row['USD Attribute'].split(':')[-1]])
        attr.SetDocumentation(row['Description'])
        attr.SetCustomDataByKey('siUnit', row['SI Unit'])
        attr.SetCustomDataByKey('synthetic', True)
        if row['Options'] != 'Not required' and row['Type'] != 'bool':
            attr.SetMetadata('allowedTokens', Vt.TokenArray([option.strip() for option in row['Options'].split('|')]))
    prim.GetAttribute('aif:spec:evaporatorLiquidMassFraction').SetCustomDataByKey('convention', 'Pure WATER uses mass fraction 1.0 in this example.')
    prim.GetAttribute('aif:spec:operatingWeight').SetCustomDataByKey('boundary', 'Synthetic filled operating mass: dry assembly 2000 kg plus 400 kg liquid.')
    prim.GetAttribute('aif:spec:shippingWeight').SetCustomDataByKey('boundary', 'Synthetic drained shipping mass: dry assembly 2000 kg plus 100 kg packaging.')
    prim.SetCustomDataByKey('coolingGridOrder', ', '.join(k.removeprefix('performanceMapCoolingGrid') for k in data if k.startswith('performanceMapCoolingGrid')))
    prim.SetCustomDataByKey('lookupOrder', 'Cartesian product; rightmost grid axis varies fastest. Illustrative maps only; no interpolation/extrapolation contract.')
    props.GetRootLayer().Save()

    geo = stage_at(layers / 'Synthetic_AC_Chiller_Geometry.usda', ROOT)
    UsdGeom.Scope.Define(geo, ROOT + '/Geometry')
    painted = material(geo, ROOT + '/Looks/PaintedMetal', (0.68, 0.74, 0.76), 0.15)
    dark = material(geo, ROOT + '/Looks/Coils', (0.055, 0.07, 0.085), 0.5)
    frame = material(geo, ROOT + '/Looks/Frame', (0.11, 0.16, 0.19), 0.5)
    steel = material(geo, ROOT + '/Looks/Steel', (0.34, 0.40, 0.44), 0.75)
    blue = material(geo, ROOT + '/Looks/Water', (0.025, 0.30, 0.55), 0.3)
    screen = material(geo, ROOT + '/Looks/Screen', (0.02, 0.12, 0.16), 0.1)
    for y in [-0.95, 0.95]:
        shape(geo, 'BaseRail_' + ('Front' if y < 0 else 'Back'), UsdGeom.Cube, (0, y, 0.22), (6.2, 0.18, 0.28), frame)
        for i, x in enumerate([-2.5, 0, 2.5]):
            shape(geo, f'Foot_{y}_{i}'.replace('-', 'N').replace('.', '_'), UsdGeom.Cube, (x, y, 0.07), (0.55, 0.4, 0.14), steel)
    shape(geo, 'CoilBody', UsdGeom.Cube, (0, 0, 1.72), (6.0, 2.3, 1.5), dark)
    for z in [0.94, 2.5]:
        shape(geo, f'HorizontalFrame_{int(z*100)}', UsdGeom.Cube, (0, 0, z), (6.1, 2.4, 0.12), painted)
    for i, x in enumerate([-2.95, -1, 1, 2.95]):
        for j, y in enumerate([-1.18, 1.18]):
            shape(geo, f'Post_{i}_{j}', UsdGeom.Cube, (x, y, 1.7), (0.10, 0.10, 1.6), painted)
    for i in range(19):
        for j, y in enumerate([-1.16, 1.16]):
            shape(geo, f'Fin_{i}_{j}', UsdGeom.Cube, (0, y, 1.04 + i*0.075), (5.85, 0.035, 0.018), steel)
    for i, x in enumerate([-2, 0, 2]):
        for j, y in enumerate([-0.61, 0.61]):
            shape(geo, f'FanHousing_{i}_{j}', UsdGeom.Cylinder, (x, y, 2.57), (0.53, 0.53, 0.16), frame)
            shape(geo, f'FanWell_{i}_{j}', UsdGeom.Cylinder, (x, y, 2.66), (0.47, 0.47, 0.025), dark)
            shape(geo, f'FanHub_{i}_{j}', UsdGeom.Cylinder, (x, y, 2.70), (0.13, 0.13, 0.07), steel)
            for blade in range(5):
                angle = blade * 72
                a = math.radians(angle)
                shape(geo, f'FanBlade_{i}_{j}_{blade}', UsdGeom.Cube,
                      (x + 0.27*math.cos(a), y + 0.27*math.sin(a), 2.69),
                      (0.33, 0.12, 0.035), steel, (0, 12, angle + 15))
    for i, x in enumerate([-1.6, 1.0], 1):
        shape(geo, f'Compressor_{i}', UsdGeom.Cylinder, (x, -0.65, 0.65), (0.26, 0.26, 1.3), frame, (0, 90, 0))
    shape(geo, 'Evaporator', UsdGeom.Cylinder, (0, 0.55, 0.62), (0.26, 0.26, 4.4), steel, (0, 90, 0))
    shape(geo, 'ControlsCabinet', UsdGeom.Cube, (3.08, 0, 1.67), (0.25, 1.1, 1.4), painted)
    shape(geo, 'ControlDisplay', UsdGeom.Cube, (3.22, -0.13, 1.9), (0.03, 0.5, 0.26), screen)
    for i, y in enumerate([-0.6, 0.6]):
        shape(geo, f'WaterPort_{i}', UsdGeom.Cylinder, (3.12, y, 0.64), (0.05715, 0.05715, 0.4), blue, (0, 90, 0))
        shape(geo, f'WaterFlange_{i}', UsdGeom.Cylinder, (3.32, y, 0.64), (0.12, 0.12, 0.04), blue, (0, 90, 0))
    geo.GetRootLayer().Save()

    root = stage_at(DEST / 'asset/Synthetic_AC_Chiller.usda', ROOT)
    root.GetRootLayer().subLayerPaths = ['layers/Synthetic_AC_Chiller_Properties.usda', 'layers/Synthetic_AC_Chiller_Geometry.usda']
    root.GetRootLayer().customLayerData = {
        'synthetic': True, 'description': 'Fictional AC_Chiller CSV example; not certified equipment performance.',
        'asset_license': 'CC-BY 4.0', 'author': 'NVIDIA',
        'source': 'Procedural geometry and illustrative data authored for this repository.',
    }
    root.GetDefaultPrim().SetMetadata('kind', 'component')
    UsdPhysics.MassAPI.Apply(root.GetDefaultPrim()).CreateMassAttr(2400.0)
    root.GetRootLayer().Save()

    preview = stage_at(DEST / 'preview.usda', '/Preview')
    ref = preview.DefinePrim('/Preview/Chiller', 'Xform')
    ref.GetReferences().AddReference('asset/Synthetic_AC_Chiller.usda')
    ground = UsdGeom.Cube.Define(preview, '/Preview/Ground')
    ground.CreateSizeAttr(1.0)
    ground.AddTranslateOp().Set((0, 0, -0.055))
    ground.AddScaleOp().Set((200, 200, 0.1))
    floor = material(preview, '/Preview/Looks/Ground', (0.15, 0.18, 0.21), 0, 0.8)
    UsdShade.MaterialBindingAPI.Apply(ground.GetPrim()).Bind(floor)
    camera = UsdGeom.Camera.Define(preview, '/Preview/Camera')
    camera.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(10, -12, 8), Gf.Vec3d(0, 0, 1.35), Gf.Vec3d(0, 0, 1)).GetInverse())
    camera.CreateFocalLengthAttr(52)
    camera.CreateHorizontalApertureAttr(36)
    camera.CreateVerticalApertureAttr(22.5)
    camera.CreateClippingRangeAttr((0.1, 1000))
    dome = UsdLux.DomeLight.Define(preview, '/Preview/Dome')
    dome.CreateIntensityAttr(0.2)
    for name, pos, intensity, size in [('Key', (1, -5, 9), 3.0, 7), ('Fill', (-5, 1, 6), 1.0, 6)]:
        light = UsdLux.RectLight.Define(preview, '/Preview/' + name)
        light.CreateIntensityAttr(intensity)
        light.CreateWidthAttr(size)
        light.CreateHeightAttr(size)
        light.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(*pos), Gf.Vec3d(0, 0, 1), Gf.Vec3d(0, 0, 1)).GetInverse())
    preview.GetRootLayer().Save()
    print(f'Built {len(rows)} synthetic attributes and geometry at {DEST}')


if __name__ == '__main__':
    build()
