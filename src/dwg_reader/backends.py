"""Discovery and safe subprocess adapters for optional CAD backends."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BackendStatus:
    name: str
    available: bool
    path: str | None
    purpose: str
    version: str | None = None


def _find(env_name: str, *commands: str, mac_path: str | None = None) -> str | None:
    configured = os.environ.get(env_name)
    if configured and Path(configured).is_file():
        return str(Path(configured).resolve())
    for command in commands:
        if found := shutil.which(command):
            return found
    if mac_path and Path(mac_path).is_file():
        return mac_path
    return None


def _version(path: str | None, *args: str) -> str | None:
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, *args], capture_output=True, text=True, timeout=10, check=False,
        )
        return (result.stdout or result.stderr).strip().splitlines()[0][:200] or None
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def discover_backends() -> dict[str, BackendStatus]:
    oda = _find(
        "DWG_READER_ODA_PATH", "ODAFileConverter",
        mac_path="/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter",
    )
    libredwg = _find("DWG_READER_LIBREDWG_PATH", "dwgread")
    openscad = _find(
        "OPENSCAD_PATH", "openscad",
        mac_path="/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
    )
    opencad = _find("OPENCAD_PATH", "opencad")
    return {
        "oda": BackendStatus("oda", bool(oda), oda, "DWG to canonical DXF"),
        "libredwg": BackendStatus(
            "libredwg", bool(libredwg), libredwg, "open-source DWG fallback",
            _version(libredwg, "--version"),
        ),
        "openscad": BackendStatus(
            "openscad", bool(openscad), openscad, "DXF extrusion, render, STL/3MF export",
            _version(openscad, "--version"),
        ),
        "opencad": BackendStatus(
            "opencad", bool(opencad), opencad, "OCCT parametric STEP/STL modeling",
            _version(opencad, "--version"),
        ),
    }


def doctor_report() -> dict[str, Any]:
    try:
        import ezdxf
        ezdxf_version = ezdxf.__version__
    except ImportError:
        ezdxf_version = None
    mcp_available = importlib.util.find_spec("mcp") is not None
    return {
        "backends": {name: asdict(status) for name, status in discover_backends().items()},
        "python": {"available": True, "version": os.sys.version.split()[0]},
        "ezdxf": {"available": ezdxf_version is not None, "version": ezdxf_version},
        "mcp": {"available": mcp_available},
    }


def openscad_extrude(
    dxf: str | Path,
    output: str | Path,
    *,
    height: float = 10.0,
    layer: str | None = None,
    convexity: int = 10,
    timeout: int = 300,
) -> dict[str, Any]:
    """Extrude a 2D DXF with OpenSCAD and export by output extension."""
    source, target = Path(dxf).resolve(), Path(output).resolve()
    if not source.is_file() or source.suffix.lower() != ".dxf":
        raise ValueError(f"DXF input not found: {source}")
    if height <= 0:
        raise ValueError("height must be greater than zero")
    backend = discover_backends()["openscad"]
    if not backend.path:
        raise ValueError("OpenSCAD not found; set OPENSCAD_PATH or install OpenSCAD")
    target.parent.mkdir(parents=True, exist_ok=True)
    layer_arg = f", layer={_scad_string(layer)}" if layer else ""
    source_code = (
        f"linear_extrude(height={height:g}, convexity={int(convexity)})\n"
        f"    import(file={_scad_string(str(source))}{layer_arg});\n"
    )
    with tempfile.TemporaryDirectory(prefix="dwg-reader-openscad-") as temp_dir:
        scad = Path(temp_dir) / "model.scad"
        scad.write_text(source_code, encoding="utf-8")
        result = subprocess.run(
            [backend.path, "-o", str(target), str(scad)],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    if result.returncode != 0 or not target.is_file():
        raise RuntimeError((result.stderr or result.stdout or "OpenSCAD export failed").strip())
    return {
        "input": str(source), "output": str(target), "height": height,
        "layer": layer, "backend": backend.path, "bytes": target.stat().st_size,
    }


def convert_dwg_file(
    source: str | Path, output_dir: str | Path, *, backend: str = "auto",
    oda_path: str | Path | None = None,
) -> dict[str, Any]:
    """Convert one DWG to DXF using ODA first or the LibreDWG fallback."""
    source_path, target_dir = Path(source).resolve(), Path(output_dir).resolve()
    if not source_path.is_file() or source_path.suffix.lower() != ".dwg":
        raise ValueError(f"DWG input not found: {source_path}")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{source_path.stem}.dxf"
    statuses = discover_backends()
    if oda_path and Path(oda_path).is_file():
        statuses["oda"] = BackendStatus("oda", True, str(Path(oda_path).resolve()),
                                        "DWG to canonical DXF")
    selected = backend
    if backend == "auto":
        selected = "oda" if statuses["oda"].available else "libredwg"
    if selected == "oda":
        executable = statuses["oda"].path
        if not executable:
            raise ValueError("ODA File Converter not found")
        command = [executable, str(source_path.parent), str(target_dir), "ACAD2018", "DXF",
                   "0", "0", source_path.name]
    elif selected == "libredwg":
        executable = statuses["libredwg"].path
        if not executable:
            raise ValueError("LibreDWG dwgread not found")
        command = [executable, "-O", "DXF", "-o", str(target), str(source_path)]
    else:
        raise ValueError(f"unsupported converter backend: {backend}")
    result = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
    if result.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError((result.stderr or result.stdout or "DWG conversion failed").strip())
    return {"input": str(source_path), "output": str(target), "backend": selected,
            "bytes": target.stat().st_size}


def _scad_string(value: str | None) -> str:
    escaped = (value or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
