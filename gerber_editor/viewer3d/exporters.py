"""Physical model export: VRML meshes and colored OpenCascade STEP solids."""

import os
import tempfile
from pathlib import Path

from gerber_editor.viewer3d.mesh import polygons


def visible_parts(mesh, hidden=()):
    return [part for part in mesh.parts if part.key not in hidden and len(part.vertices)]


def export_wrl(mesh, path, hidden=()):
    path = Path(path)
    parts = visible_parts(mesh, hidden)
    if not parts:
        raise ValueError("Nenhum material visível para exportar.")
    fd, temporary = tempfile.mkstemp(prefix=".editor-gerber-", suffix=".wrl", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(
                '#VRML V2.0 utf8\n# Editor Gerber: SI metres, original XY origin.\nWorldInfo { title "Editor Gerber PCB" }\n'
            )
            for part in parts:
                r, g, b = part.color
                stream.write(
                    f"Shape {{ appearance Appearance {{ material Material {{ diffuseColor {r} {g} {b} specularColor 0.25 0.25 0.25 shininess 0.35 }} }}\ngeometry IndexedFaceSet {{ solid FALSE coord Coordinate {{ point [\n"
                )
                for vertex in part.vertices:
                    x, y, z = vertex[:3]
                    stream.write(
                        f"{(float(x) + mesh.center[0]) * 0.001:.10g} {(float(y) + mesh.center[1]) * 0.001:.10g} {float(z) * 0.001:.10g},\n"
                    )
                stream.write("] } coordIndex [\n")
                for index in range(0, len(part.vertices), 3):
                    stream.write(f"{index}, {index + 1}, {index + 2}, -1,\n")
                stream.write("] } }\n")
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def step_available():
    import importlib.util

    return importlib.util.find_spec("OCP") is not None


def export_step(mesh, path, hidden=()):
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCP.ShapeFix import ShapeFix_Shape
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS_Compound
    from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_DocumentTool
    from shapely import make_valid, set_precision
    from shapely.geometry.polygon import orient

    parts = visible_parts(mesh, hidden)
    if not parts:
        raise ValueError("Nenhum material visível para exportar.")
    document = TDocStd_Document(TCollection_ExtendedString("Editor Gerber"))
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
    root = shapes.NewShape()
    TDataStd_Name.Set_s(root, TCollection_ExtendedString("Editor Gerber PCB"))
    edges = 0
    for part in parts:
        if part.geometry is None or part.geometry.is_empty:
            continue
        compound = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(compound)
        for polygon in polygons(make_valid(set_precision(part.geometry, 0.000001))):
            if polygon.area < 0.0000000001:
                continue
            polygon = orient(polygon, sign=1)

            def wire(ring, z=part.z_min):
                nonlocal edges
                maker = BRepBuilderAPI_MakePolygon()
                for x, y in list(ring.coords)[:-1]:
                    maker.Add(gp_Pnt(x, y, z))
                    edges += 1
                if edges > 250000:
                    raise ValueError(
                        "STEP muito complexo. Escolha detalhe Rápido ou oculte materiais."
                    )
                maker.Close()
                if not maker.IsDone():
                    raise ValueError("Não foi possível criar um contorno STEP.")
                return maker.Wire()

            face = BRepBuilderAPI_MakeFace(wire(polygon.exterior))
            for hole in polygon.interiors:
                face.Add(wire(hole))
            solid = BRepPrimAPI_MakePrism(
                face.Face(), gp_Vec(0, 0, max(0.001, part.z_max - part.z_min))
            ).Shape()
            if not BRepCheck_Analyzer(solid).IsValid():
                fixer = ShapeFix_Shape(solid)
                fixer.SetPrecision(0.0000001)
                fixer.SetMaxTolerance(0.000001)
                fixer.Perform()
                solid = fixer.Shape()
                properties = GProp_GProps()
                BRepGProp.VolumeProperties_s(solid, properties)
                expected = polygon.area * max(0.001, part.z_max - part.z_min)
                if not BRepCheck_Analyzer(solid).IsValid() or abs(
                    properties.Mass() - expected
                ) > max(0.0000001, expected * 0.000001):
                    raise ValueError("Sólido STEP inválido; exportação cancelada. " + part.name)
            builder.Add(compound, solid)
        label = shapes.AddShape(compound, False)
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(part.name))
        colors.SetColor(label, Quantity_Color(*part.color, Quantity_TOC_RGB), XCAFDoc_ColorGen)
        component = shapes.AddComponent(root, label, TopLoc_Location())
        TDataStd_Name.Set_s(component, TCollection_ExtendedString(part.name))
        colors.SetColor(component, Quantity_Color(*part.color, Quantity_TOC_RGB), XCAFDoc_ColorGen)
    shapes.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    writer.Transfer(document, STEPControl_AsIs)
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".editor-gerber-", suffix=".step", dir=path.parent)
    os.close(fd)
    try:
        if writer.Write(temporary) != IFSelect_RetDone:
            raise OSError("Não foi possível gravar STEP.")
        reader = STEPControl_Reader()
        if reader.ReadFile(temporary) != IFSelect_RetDone or reader.TransferRoots() == 0:
            raise ValueError("Não foi possível reabrir o STEP gerado.")
        if not BRepCheck_Analyzer(reader.OneShape()).IsValid():
            raise ValueError("STEP inválido após reabertura.")
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
