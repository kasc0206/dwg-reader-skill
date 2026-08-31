"""Unified command-line interface."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import __version__
from .backends import convert_dwg_file, doctor_report, openscad_extrude
from .fonts import get_font
from .report import inspect_report, text_dict
from .stream import extract_texts

DEFAULT_ODA = Path("/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dwg-reader", description="Read DWG/DXF drawings")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    text = commands.add_parser("text", help="stream text from a DXF file")
    text.add_argument("input", type=Path)
    text.add_argument("legacy_output", nargs="?", type=Path, help=argparse.SUPPRESS)
    text.add_argument("-o", "--output", type=Path)
    text.add_argument("--font", help="SHX path or bundled font name")
    text.add_argument("--with-metadata", action="store_true")
    text.add_argument("--format", choices=("text", "json"), default="text")
    text.add_argument("--expand-blocks", action="store_true")
    text.add_argument("--max-depth", type=int, default=8)

    inspect = commands.add_parser("inspect", help="inspect entities using ezdxf")
    inspect.add_argument("input", type=Path)
    inspect.add_argument("--entities", action="store_true")
    inspect.add_argument("--texts", action="store_true")
    inspect.add_argument("--layers", action="store_true")
    inspect.add_argument("--blocks", action="store_true")
    inspect.add_argument("--limits", action="store_true")
    inspect.add_argument("-o", "--output", type=Path)
    inspect.add_argument("--format", choices=("text", "json"), default="text")
    inspect.add_argument("--expand-blocks", "--explode-blocks", action="store_true")
    inspect.add_argument("--max-depth", type=int, default=8)

    convert = commands.add_parser("convert", help="convert a DWG file or directory to DXF")
    convert.add_argument("input", type=Path)
    convert.add_argument("output", type=Path)
    convert.add_argument("--version", default="ACAD2018")
    convert.add_argument("--recursive", action="store_true")
    convert.add_argument("--audit", action="store_true")
    convert.add_argument("--oda", type=Path, default=DEFAULT_ODA)
    convert.add_argument("--backend", choices=("auto", "oda", "libredwg"), default="auto")

    font = commands.add_parser("font", help="inspect a bundled or explicit SHX font")
    font.add_argument("name")
    font.add_argument("codes", nargs="*")

    doctor = commands.add_parser("doctor", help="detect optional CAD backends")
    doctor.add_argument("--format", choices=("text", "json"), default="text")

    scad = commands.add_parser("openscad", help="extrude a 2D DXF with OpenSCAD")
    scad.add_argument("input", type=Path)
    scad.add_argument("output", type=Path)
    scad.add_argument("--height", type=float, default=10.0)
    scad.add_argument("--layer")
    scad.add_argument("--convexity", type=int, default=10)
    scad.add_argument("--timeout", type=int, default=300)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "text":
            return _text(args)
        if args.command == "convert":
            return _convert(args)
        if args.command == "font":
            return _font(args)
        if args.command == "doctor":
            return _doctor(args)
        if args.command == "openscad":
            return _openscad(args)
        return _inspect(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _text(args: argparse.Namespace) -> int:
    explicit = get_font(args.font) if args.font else None
    if args.font and explicit is None:
        raise ValueError(f"font not found or unsupported: {args.font}")
    if args.expand_blocks:
        report = inspect_report(args.input, expand_blocks=True, max_depth=args.max_depth)
        records_json = report["texts"]
    else:
        records = extract_texts(args.input, font=explicit)
        records_json = [text_dict(record) for record in records]
    if args.format == "json":
        output = json.dumps({"texts": records_json}, ensure_ascii=False, indent=2)
    elif args.with_metadata:
        output = "\n".join(
            f"{r['y']:g}\t{r['x']:g}\t{r['entity']}\t{r['layer']}\t{r['text']}"
            for r in records_json
        )
    else:
        output = "\n".join(f"[{record['text']}]" for record in records_json)
    output_path = args.output or args.legacy_output
    if output_path:
        output_path.write_text(output, encoding="utf-8")
    else:
        print(output)
    print(f"extracted {len(records_json)} text records", file=sys.stderr)
    return 0


def _convert(args: argparse.Namespace) -> int:
    if args.input.is_file():
        result = convert_dwg_file(
            args.input, args.output, backend=args.backend, oda_path=args.oda,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not args.oda.is_file():
        raise ValueError(f"ODA File Converter not found: {args.oda}")
    source = args.input.resolve()
    if source.is_file():
        input_dir, pattern = source.parent, source.name
    elif source.is_dir():
        input_dir, pattern = source, "*.dwg"
    else:
        raise ValueError(f"input not found: {source}")
    args.output.mkdir(parents=True, exist_ok=True)
    command = [
        str(args.oda), str(input_dir), str(args.output.resolve()), args.version, "DXF",
        str(int(args.recursive)), str(int(args.audit)), pattern,
    ]
    return subprocess.run(command, check=False).returncode


def _font(args: argparse.Namespace) -> int:
    font = get_font(args.name)
    if not font:
        raise ValueError(f"font not found or unsupported: {args.name}")
    kind = "bigfont" if font.is_bigfont else "unifont"
    print(f"{font.name}: type={kind}, encoding={font.encoding}, shapes={len(font)}")
    for token in args.codes:
        code = int(token, 16)
        print(f"0x{code:04X}\t{font.get_char(code) or ''}")
    return 0


def _doctor(args: argparse.Namespace) -> int:
    report = doctor_report()
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    for name, status in report["backends"].items():
        state = "ok" if status["available"] else "missing"
        detail = status["path"] or status["purpose"]
        print(f"{name}\t{state}\t{detail}")
    for name in ("python", "ezdxf", "mcp"):
        status = report[name]
        print(f"{name}\t{'ok' if status['available'] else 'missing'}\t{status.get('version') or ''}")
    return 0


def _openscad(args: argparse.Namespace) -> int:
    result = openscad_extrude(
        args.input, args.output, height=args.height, layer=args.layer,
        convexity=args.convexity, timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _inspect(args: argparse.Namespace) -> int:
    report = inspect_report(args.input, expand_blocks=args.expand_blocks, max_depth=args.max_depth)
    if args.format == "json":
        output = json.dumps(report, ensure_ascii=False, indent=2)
    else:
        drawing = report["drawing"]
        lines = [
            f"file: {drawing['file']}", f"version: {drawing['dxf_version']}",
            f"entities: {drawing['entity_count']}", f"types: {drawing['entity_types']}",
        ]
        if args.layers:
            lines.extend(f"layer\t{x['name']}\tcolor={x['color']}\tlinetype={x['linetype']}"
                         for x in report["layers"])
        if args.blocks:
            lines.extend(f"block\t{x['name']}\tentities={x['entity_count']}"
                         for x in report["blocks"])
        if args.texts:
            lines.extend(f"text\t{x['x']:g},{x['y']:g}\t{x['text']}" for x in report["texts"])
        if args.limits:
            lines.append(f"limits\t{drawing['extents']['min']}\t{drawing['extents']['max']}")
        if args.entities:
            lines.append("entity details are available in JSON output")
        output = "\n".join(lines)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
