#!/usr/bin/env python3
import os
import json
import sys
import re
import math
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from jinja2 import Environment, FileSystemLoader

_RADIX_MAP = {'DEC': 'DEC', 'HEX': 'HEX', 'BIN': 'BIN', 'OCT': 'OCT', 'UNS': 'UNS'}

# Valid (width, depth) combinations - 25 configs total
# Group 1 (4096 bits): 1x4096, 2x2048, 4x1024, 8x512, 16x256
# Group 2 (8192 bits): 2x4096, 4x2048, 8x1024, 16x512, 32x256
# Group 3 (16384 bits): 4x4096, 8x2048, 16x1024, 32x512, 64x256
# Group 4 (32768 bits): 8x4096, 16x2048, 32x1024, 64x512, 128x256
# Group 5 (65536 bits): 16x4096, 32x2048, 64x1024, 128x512, 256x256
_VALID_COMBINATIONS = {
    (1, 4096), (2, 2048), (4, 1024), (8, 512), (16, 256),
    (2, 4096), (4, 2048), (8, 1024), (16, 512), (32, 256),
    (4, 4096), (8, 2048), (16, 1024), (32, 512), (64, 256),
    (8, 4096), (16, 2048), (32, 1024), (64, 512), (128, 256),
    (16, 4096), (32, 2048), (64, 1024), (128, 512), (256, 256)
}

def _validate_combination(width: int, depth: int, port_name: str = "port") -> bool:
    return (width, depth) in _VALID_COMBINATIONS

def _parse_data(data_str: str, data_radix: str) -> int:
    data_str = data_str.strip()
    if data_radix == 'HEX':
        return int(data_str, 16) if not data_str.startswith('0x') else int(data_str, 16)
    elif data_radix == 'BIN':
        return int(data_str, 2) if not data_str.startswith('0b') else int(data_str, 2)
    elif data_radix == 'OCT':
        return int(data_str, 8) if not data_str.startswith('0o') else int(data_str, 8)
    elif data_radix == 'UNS':
        return int(data_str)
    else:
        return int(data_str)

def read_mif(path: str) -> Dict[str, Any]:
    result = {
        'mode': 'unknown', 'width': 0, 'depth': 0, 'widthA': 0, 'widthB': 0,
        'depthA': 0, 'depthB': 0, 'address_radix': 'DEC', 'data_radix': 'HEX',
        'data_dict': {}, 'data_array': [], 'hex_strings': [], 'success': False, 'error': None
    }
    try:
        if not os.path.exists(path):
            raise FileNotFoundError(f"not found: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        in_content = False
        for line in lines:
            line = line.strip()
            if not line or line.startswith('--'):
                continue
            if 'CONTENT BEGIN' in line.upper():
                in_content = True
                continue
            elif 'END;' in line.upper():
                break
            if not in_content:
                line = line.rstrip(';').strip()
                line_upper = line.upper()
                if result['mode'] == 'unknown':
                    if 'WIDTHA=' in line_upper and 'DEPTHA=' in ''.join(lines).upper():
                        result['mode'] = 'dual'
                    elif 'WIDTH=' in line_upper and 'DEPTH=' in ''.join(lines).upper():
                        result['mode'] = 'single'
                for param, key in [('WIDTH=', 'width'), ('DEPTH=', 'depth'), ('WIDTHA=', 'widthA'),
                                   ('WIDTHB=', 'widthB'), ('DEPTHA=', 'depthA'), ('DEPTHB=', 'depthB')]:
                    if line_upper.startswith(param):
                        result[key] = int(line.split('=')[1].strip())
                if line_upper.startswith('ADDRESS_RADIX='):
                    result['address_radix'] = _RADIX_MAP.get(line.split('=')[1].strip().upper(), 'DEC')
                elif line_upper.startswith('DATA_RADIX='):
                    result['data_radix'] = _RADIX_MAP.get(line.split('=')[1].strip().upper(), 'HEX')
            else:
                line = line.split('--')[0].strip() if '--' in line else line.strip()
                if not (line := line.rstrip(';').strip()):
                    continue
                if range_match := re.match(r'\[(.+?)\s*\.\.\s*(.+?)\]\s*:\s*([^;]+);?', line):
                    start_addr_str, end_addr_str, data_str = range_match.group(1), range_match.group(2), range_match.group(3).strip()
                    start_addr = _parse_data(start_addr_str, result['address_radix'])
                    end_addr = _parse_data(end_addr_str, result['address_radix'])
                    data_value = _parse_data(data_str, result['data_radix'])
                    for addr in range(start_addr, end_addr + 1):
                        result['data_dict'][addr] = data_value
                elif single_match := re.match(r'(.+?)\s*:\s*([^;]+);?', line):
                    addr_str, data_str = single_match.group(1), single_match.group(2).strip()
                    addr = _parse_data(addr_str, result['address_radix'])
                    data_value = _parse_data(data_str, result['data_radix'])
                    result['data_dict'][addr] = data_value
        if result['mode'] == 'unknown':
            result['mode'] = 'dual' if (result['widthA'] > 0 or result['widthB'] > 0) else 'single' if result['width'] > 0 else None
        if not result['mode']:
            raise ValueError("Width and Depth parameters not found in MIF file")
        
        if result['mode'] == 'single':
            if result['width'] <= 0 or result['depth'] <= 0:
                raise ValueError(f"Single-port mode parameters invalid: width={result['width']}, depth={result['depth']}")
            if not _validate_combination(result['width'], result['depth']):
                raise ValueError(f"Invalid single-port combination: width={result['width']}, depth={result['depth']}. Must be one of: {sorted(_VALID_COMBINATIONS)}")
            depth = result['depth']
            width = result['width']
        else:
            if result['widthA'] <= 0 or result['depthA'] <= 0 or result['widthB'] <= 0 or result['depthB'] <= 0:
                raise ValueError(f"Dual-port mode parameters invalid: A(w={result['widthA']},d={result['depthA']}), B(w={result['widthB']},d={result['depthB']})")
            if not _validate_combination(result['widthA'], result['depthA']):
                raise ValueError(f"Invalid dual-port combination for port A: width={result['widthA']}, depth={result['depthA']}. Must be one of: {sorted(_VALID_COMBINATIONS)}")
            if not _validate_combination(result['widthB'], result['depthB']):
                raise ValueError(f"Invalid dual-port combination for port B: width={result['widthB']}, depth={result['depthB']}. Must be one of: {sorted(_VALID_COMBINATIONS)}")
            if (result['widthA'] * result['depthA']) != (result['widthB'] * result['depthB']):
                raise ValueError("Dual-port capacity mismatch")
            depth = result['depthA']
            width = result['widthA']
        
        data_array = [0] * depth
        for addr, value in result['data_dict'].items():
            if 0 <= addr < depth:
                data_array[addr] = value
        result['data_array'] = data_array
        hex_chars = (width + 3) // 4
        max_val = (1 << width) - 1
        result['hex_strings'] = [format(min(value, max_val), f'0{hex_chars}x') for value in data_array]
        result['success'] = True
    except Exception as e:
        result['error'] = str(e)
    return result

def generate_bram_ip(module_name: str, width_A: int, depth_A: int, width_B: int, depth_B: int, raw_data_array: list) -> dict:
    """
    Generate BRAM IP Verilog code.
    
    Args:
        module_name: Name of the module
        width_A: Width of port A
        depth_A: Depth of port A
        width_B: Width of port B (0 for single-port)
        depth_B: Depth of port B (1 for single-port)
        raw_data_array: Initial data array
    
    Returns:
        Dictionary with result information
    """
    try:
        template_dir = os.path.dirname(os.path.abspath(__file__))
        env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)
        env.filters['format_hex'] = lambda x: f"{x:02X}"
        template = env.get_template('templates/bram_template.j2')
        module_number = int(width_A * depth_A / 4096)
        width_A_one, width_B_one = int(width_A/module_number), int(width_B/module_number)
        
        # Each RAM module is 4KB (4096 bits), organized as 16 INIT params x 256 bits each
        # Calculate how many addresses fit in one INIT param based on width
        # For width=1: 256 addresses per INIT (256 bits / 1 bit = 256)
        # For width=4: 64 addresses per INIT (256 bits / 4 bits = 64)
        # For width=8: 32 addresses per INIT (256 bits / 8 bits = 32)
        # For width=16: 16 addresses per INIT (256 bits / 16 bits = 16)
        addresses_per_init = 256 // width_A_one
        init_lines_per_instance = (depth_A + addresses_per_init - 1) // addresses_per_init
        
        init_data = []
        
        for module_idx in range(module_number):
            module_init_strings = []
            
            # For multi-module configs, extract the data bits for this module
            # Each module handles a slice of the data width
            bit_start = module_idx * width_A_one
            
            for group_idx in range(init_lines_per_instance):
                start_addr = group_idx * addresses_per_init
                end_addr = min(start_addr + addresses_per_init, depth_A)
                
                # Collect data for this group, from highest address to lowest (for INIT format)
                group_binary_str = ''
                for addr in range(end_addr - 1, start_addr - 1, -1):
                    # Extract the data for this module from the raw data
                    if addr < len(raw_data_array):
                        data_val = (raw_data_array[addr] >> bit_start) & ((1 << width_A_one) - 1)
                    else:
                        data_val = 0
                    group_binary_str += format(data_val, f'0{width_A_one}b')
                
                # Pad to 256 bits if necessary
                if end_addr - start_addr < addresses_per_init:
                    padding_bits = (addresses_per_init - (end_addr - start_addr)) * width_A_one
                    group_binary_str += '0' * padding_bits
                
                # Convert binary string to hex (256 bits = 64 hex digits)
                hex_str = ''.join(format(int(group_binary_str[i:i+4], 2), 'x') for i in range(0, 256, 4))
                module_init_strings.append(f"256'h{hex_str}")
            
            init_data.append(module_init_strings)
        
        template_params = {
            'module_name': module_name, 'width_A': width_A, 'depth_A': int(math.log2(depth_A)),
            'width_A_one': width_A_one, 'width_B': width_B, 'depth_B': int(math.log2(depth_B)),
            'width_B_one': width_B_one, 'init_data': init_data, 'module_number': module_number,
            'generation_date': datetime.now().strftime("%Y.%m.%d")
        }
        
        verilog_code = template.render(**template_params)
        
        return {
            'success': True,
            'verilog_code': verilog_code,
            'message': f"BRAM IP generated successfully: {module_name}.v"
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': f"Failed to generate BRAM IP: {e}"
        }

def generate_bram_from_mif(mif_file: str, output_file: Optional[str] = None) -> dict:
    """
    Generate BRAM IP from MIF file.
    
    Args:
        mif_file: Path to MIF file
        output_file: Optional output file path
    
    Returns:
        Dictionary with result information
    """
    mif_result = read_mif(mif_file)
    module_name = os.path.splitext(os.path.basename(mif_file))[0]
    
    if not mif_result['success']:
        return {
            'success': False,
            'error': mif_result['error'],
            'message': f"Failed to read MIF file: {mif_result['error']}"
        }
    
    try:
        width_A = mif_result['width'] if mif_result['mode'] == 'single' else mif_result['widthA']
        depth_A = mif_result['depth'] if mif_result['mode'] == 'single' else mif_result['depthA']
        width_B = 0 if mif_result['mode'] == 'single' else mif_result['widthB']
        depth_B = 1 if mif_result['mode'] == 'single' else mif_result['depthB']
        
        result = generate_bram_ip(module_name, width_A, depth_A, width_B, depth_B, mif_result['data_array'])
        
        if result['success']:
            output_path = output_file or f"{module_name}.v"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result['verilog_code'])
            
            return {
                'success': True,
                'output_file': output_path,
                'message': f"BRAM IP generated successfully: {output_path}"
            }
        else:
            return result
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': f"Failed to generate BRAM IP: {e}"
        }

def main(args_list: Optional[list[str]] = None) -> int:
    """
    Main entry point for BRAM generator.
    
    Args:
        args_list: Optional command line arguments (for programmatic use)
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(description='Generate BRAM IP Verilog code')
    
    parser.add_argument('mif_file', type=str, help='Input MIF file path')
    parser.add_argument('--output', type=str, help='Output Verilog file')
    
    args = parser.parse_args(args_list)
    
    result = generate_bram_from_mif(args.mif_file, args.output)
    print(json.dumps(result))
    
    return 0 if result['success'] else 1

if __name__ == '__main__':
    sys.exit(main())
