#!/usr/bin/env python3

from PIL import Image
import argparse
import os


def threshold_transform(x):
    return 0 if x < 128 else 255


def generate_preview(data, output_path):
    if len(data) != 1024:
        raise ValueError(f"Data size must be 1024 bytes, got {len(data)}")
    
    preview = Image.new('1', (128, 64), 1)
    pixels = preview.load()
    
    if pixels is None:
        raise RuntimeError("Failed to create preview pixel buffer")
    
    for tile_x in range(16):
        base_x = tile_x * 8
        base_addr = tile_x * 64
        
        for row in range(64):
            addr = base_addr + row
            byte_val = data[addr]
            y = row
            
            for col in range(8):
                x = base_x + col
                if byte_val & (1 << (7 - col)):
                    pixels[x, y] = 0
    
    preview.save(output_path)
    print(f"Preview saved: {output_path}")


def generate_preview_from_mif(mif_path, output_path):
    data = parse_mif_file(mif_path)
    
    if len(data) != 1024:
        print(f"Warning: MIF data size is {len(data)}, expected 1024 bytes")
    
    generate_preview(data, output_path)


def parse_mif_file(mif_path):
    data = []
    in_content = False
    
    with open(mif_path, 'r') as f:
        for line in f:
            line = line.strip()
            
            if not line or line.startswith('--'):
                continue
            
            if line.upper().startswith('CONTENT BEGIN'):
                in_content = True
                continue
            
            if line.upper() == 'END;':
                in_content = False
                continue
            
            if in_content and ':' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    value_str = parts[1].strip().rstrip(';')
                    try:
                        value = int(value_str, 16)
                        data.append(value)
                    except ValueError:
                        pass
    
    return data


def resize_keep_aspect(img, target_size):
    target_w, target_h = target_size
    img_w, img_h = img.size
    
    scale_w = target_w / img_w
    scale_h = target_h / img_h
    scale = min(scale_w, scale_h)
    
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    result = Image.new('L', target_size, 255)
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    result.paste(resized, (offset_x, offset_y))
    
    return result


def image_to_mif(image_path, output_path, invert_color=False):
    img = Image.open(image_path)
    img = img.convert('L')
    img = resize_keep_aspect(img, (128, 64))
    img = img.point(threshold_transform, '1')
    
    pixels = img.load()
    if pixels is None:
        raise RuntimeError("Failed to load pixel data from image")
    
    data = []
    
    print(f"Processing image: {image_path}")
    print(f"Size: {img.size}")
    print("Storage mode: 8-column vertical strip (bit-reversed: bit7=left, bit0=right)")
    
    for tile_x in range(16):
        base_x = tile_x * 8
        
        for row in range(64):
            byte_val = 0
            y = row
            
            for col in range(8):
                x = base_x + col
                
                pixel = pixels[x, y]
                if pixel is None:
                    pixel = 255
                
                is_black = (pixel == 0)
                
                if invert_color:
                    is_black = not is_black
                
                if is_black:
                    byte_val |= (1 << (7 - col))
            
            data.append(byte_val)
    
    depth = len(data)
    print(f"\nGenerating MIF file: {output_path}")
    print(f"Total depth: {depth} bytes (0x{depth:04X})")
    
    with open(output_path, 'w') as f:
        f.write("-- GraphicLCD 8-Column Vertical Strip MIF File\n")
        f.write(f"-- Source image: {os.path.basename(image_path)}\n")
        f.write("-- Format: 128x64 pixels, 8-column vertical strip mode\n")
        f.write("-- Each strip: 64 bytes (64 rows, each row = 8 horizontal pixels)\n")
        f.write("-- Bit7 = leftmost pixel in row, Bit0 = rightmost pixel in row\n")
        f.write("-- Address order: 8-column strip (left-to-right), then row top-to-bottom\n\n")
        
        f.write("WIDTH=8;\n")
        f.write(f"DEPTH={depth};\n\n")
        f.write("ADDRESS_RADIX=HEX;\n")
        f.write("DATA_RADIX=HEX;\n\n")
        f.write("CONTENT BEGIN\n")
        
        for i, val in enumerate(data):
            f.write(f"    {i:04X} : {val:02X};\n")
        
        f.write("END;\n")
    
    print("MIF generation done!")
    return output_path


def generate_test_pattern(output_path, pattern='checker'):
    print(f"Generating test pattern: {pattern}")
    
    data = []
    
    for tile_x in range(16):
        base_x = tile_x * 8
        
        for row in range(64):
            byte_val = 0
            y = row
            
            for col in range(8):
                x = base_x + col
                
                if pattern == 'checker':
                    is_black = ((x // 8) + (y // 8)) % 2 == 0
                elif pattern == 'vertical':
                    is_black = (x % 2) == 0
                elif pattern == 'horizontal':
                    is_black = (y % 2) == 0
                elif pattern == 'gradient':
                    is_black = x < y
                else:
                    is_black = False
                
                if is_black:
                    byte_val |= (1 << (7 - col))
            
            data.append(byte_val)
    
    with open(output_path, 'w') as f:
        f.write("WIDTH=8;\n")
        f.write(f"DEPTH={len(data)};\n")
        f.write("ADDRESS_RADIX=HEX;\n")
        f.write("DATA_RADIX=HEX;\n")
        f.write("CONTENT BEGIN\n")
        for i, val in enumerate(data):
            f.write(f"    {i:04X} : {val:02X};\n")
        f.write("END;\n")
    
    print(f"Test pattern saved: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert image to GraphicLCD MIF file with preview')
    parser.add_argument('input', nargs='?', help='Input image path (PNG/JPG/BMP)')
    parser.add_argument('-o', '--output', help='Output MIF filename (default: input name with .mif extension)')
    parser.add_argument('-p', '--preview', help='Generate preview image from MIF (specify output PNG path)')
    parser.add_argument('-i', '--invert', action='store_true', help='Invert color (black to white)')
    parser.add_argument('-t', '--test', choices=['checker', 'vertical', 'horizontal', 'gradient'], 
                       help='Generate test pattern instead of converting from image')
    
    args = parser.parse_args()
    
    if args.test:
        mif_path = args.output if args.output else f'{args.test}.mif'
        generate_test_pattern(mif_path, args.test)
        
        if args.preview:
            generate_preview_from_mif(mif_path, args.preview)
    elif args.input:
        mif_path = args.output if args.output else args.input.rsplit('.', 1)[0] + '.mif'
        image_to_mif(args.input, mif_path, args.invert)
        
        if args.preview:
            print()
            generate_preview_from_mif(mif_path, args.preview)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python img2mif.py image.png                    # Generate MIF only")
        print("  python img2mif.py image.png -o out.mif         # Specify output name")
        print("  python img2mif.py image.png -p preview.png     # Generate MIF + preview from MIF")
        print("  python img2mif.py -t checker -o test.mif -p preview.png")
