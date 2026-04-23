#!/usr/bin/env python3
"""
Unified IP Generator

A unified entry point for generating BRAM and PLL IP modules.
This reduces bundle size by sharing the Jinja2 engine.

Usage:
    # BRAM generation
    python ip_main.py bram <mif_file> [--output <file>]
    
    # PLL generation
    python ip_main.py pll --divide <value> --gates <30|50> [--output <file>]
    python ip_main.py pll --all [--output-dir <dir>]
    
    # Show help
    python ip_main.py --help
    python ip_main.py bram --help
    python ip_main.py pll --help
"""

import sys
import json
import argparse
from typing import Optional

import bram_generator
import pll_generator


def handle_bram(args) -> int:
    result = bram_generator.generate_bram_from_mif(args.mif_file, args.output)
    print(json.dumps(result))
    return 0 if result['success'] else 1


def handle_pll(args) -> int:
    if args.all:
        result = pll_generator.generate_all_combinations(args.output_dir)
        print(json.dumps(result))
        return 0 if result['success'] else 1
    else:
        result = pll_generator.generate_pll(args.divide, args.gates, args.output)
        print(json.dumps(result))
        return 0 if result['success'] else 1


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='ip_main',
        description='Unified IP Generator - Generate BRAM and PLL Verilog modules',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate BRAM from MIF file
    python ip_main.py bram input.mif --output bram_output.v
    
    # Generate single PLL
    python ip_main.py pll --divide 2 --gates 30 --output PLL_2_30.v
    
    # Generate all PLL combinations
    python ip_main.py pll --all --output-dir ./generated
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='IP type to generate')
    
    bram_parser = subparsers.add_parser(
        'bram',
        help='Generate BRAM IP from MIF file',
        description='Generate BRAM (Block RAM) IP Verilog code from a Memory Initialization File (.mif)'
    )
    bram_parser.add_argument(
        'mif_file',
        type=str,
        help='Path to the input MIF file'
    )
    bram_parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output Verilog file path (default: <mif_name>.v)'
    )
    
    pll_parser = subparsers.add_parser(
        'pll',
        help='Generate PLL IP',
        description='Generate PLL (Phase-Locked Loop) IP Verilog code'
    )
    
    pll_group = pll_parser.add_mutually_exclusive_group(required=True)
    pll_group.add_argument(
        '--divide', '-d',
        type=int,
        choices=pll_generator.VALID_DIVIDE_VALUES,
        help=f"Divide by value. Choices: {pll_generator.VALID_DIVIDE_VALUES}"
    )
    pll_group.add_argument(
        '--all', '-a',
        action='store_true',
        help='Generate all valid PLL combinations'
    )
    
    pll_parser.add_argument(
        '--gates', '-g',
        type=int,
        choices=pll_generator.VALID_FPGA_GATES,
        help=f"FPGA gate count (30 for 30W, 50 for 50W). Choices: {pll_generator.VALID_FPGA_GATES}"
    )
    
    pll_parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path (for single PLL generation)'
    )
    
    pll_parser.add_argument(
        '--output-dir',
        type=str,
        default='.',
        help='Output directory for --all mode (default: current directory)'
    )
    
    return parser


def main(args_list: Optional[list[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(args_list)
    
    if args.command is None:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'bram':
            return handle_bram(args)
        elif args.command == 'pll':
            return handle_pll(args)
        else:
            parser.print_help()
            return 1
    except Exception as e:
        result = {
            'success': False,
            'error': str(e),
            'message': f"Unexpected error: {e}"
        }
        print(json.dumps(result))
        return 1


if __name__ == '__main__':
    sys.exit(main())
