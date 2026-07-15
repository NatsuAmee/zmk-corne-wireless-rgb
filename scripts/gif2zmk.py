#!/usr/bin/env python3
import os
import sys

# Auto-detect and use .venv if it exists
script_dir = os.path.dirname(os.path.abspath(__file__))
venv_python = os.path.join(os.path.dirname(script_dir), '.venv', 'bin', 'python3')
if os.path.exists(venv_python) and sys.executable != venv_python:
    os.execv(venv_python, [venv_python] + sys.argv)

import argparse
try:
    from PIL import Image, ImageFilter
except ImportError:
    print("Error: Pillow library not found. Please install it using 'pip install Pillow'")
    sys.exit(1)

def image_to_lvgl_1bit(img, name, frame_idx):
    width, height = img.size
    
    # Calculate bytes per row (padded to full byte)
    bytes_per_row = (width + 7) // 8
    
    pixel_data = []
    
    for y in range(height):
        row_byte = 0
        bit_idx = 0
        for x in range(width):
            # PIL '1' mode: 0 is black, 255 is white.
            pixel = img.getpixel((x, y))
            # If white (255), set bit (1 is white, 0 is black in LVGL with standard palette)
            if pixel > 0:
                row_byte |= (1 << (7 - bit_idx))
                
            bit_idx += 1
            if bit_idx == 8:
                pixel_data.append(row_byte)
                row_byte = 0
                bit_idx = 0
                
        # Pad the remaining bits in the row
        if bit_idx > 0:
            pixel_data.append(row_byte)

    # Create C array string
    c_array = f"const uint8_t {name}_{frame_idx}_data[] = {{\n"
    
    # Add palette (color 0: black, color 1: white)
    palette = [
        0x00, 0x00, 0x00, 0xff, # Black
        0xff, 0xff, 0xff, 0xff  # White
    ]
    c_array += "    /*Palette*/\n    "
    c_array += ", ".join(f"0x{b:02x}" for b in palette) + ",\n"
    
    c_array += "    /*Pixel Data*/\n    "
    for i, b in enumerate(pixel_data):
        c_array += f"0x{b:02x}, "
        if (i + 1) % 12 == 0:
            c_array += "\n    "
    c_array += "\n};\n\n"
    
    c_struct = f"""const lv_img_dsc_t {name}_{frame_idx} = {{
    .header.always_zero = 0,
    .header.w = {width},
    .header.h = {height},
    .data_size = sizeof({name}_{frame_idx}_data) - 8,
    .header.cf = LV_IMG_CF_INDEXED_1BIT,
    .data = {name}_{frame_idx}_data,
}};
"""
    return c_array + c_struct

def process_gif(input_path, output_name, target_w, target_h, rotate, outdir, threshold=None, edge_detect=False, skip_frames=0, resample_method=Image.Resampling.LANCZOS):
    try:
        gif = Image.open(input_path)
    except Exception as e:
        print(f"Error opening GIF: {e}")
        sys.exit(1)
        
    frames = []
    
    try:
        while True:
            # Convert frame to RGBA first to handle transparency
            frame = gif.convert('RGBA')
            
            # Create a white background (if original had transparency)
            bg = Image.new('RGBA', frame.size, (255, 255, 255, 255))
            bg.paste(frame, mask=frame.split()[3])
            frame = bg.convert('RGB')
            
            # Resize (contain style: preserve aspect ratio, pad with white)
            img_w, img_h = frame.size
            ratio = min(target_w / img_w, target_h / img_h)
            new_w = max(1, int(img_w * ratio))
            new_h = max(1, int(img_h * ratio))
            frame = frame.resize((new_w, new_h), resample_method)
            
            # Create a target canvas and paste the resized frame in the center
            new_frame = Image.new('RGB', (target_w, target_h), (255, 255, 255))
            new_frame.paste(frame, ((target_w - new_w) // 2, (target_h - new_h) // 2))
            frame = new_frame
            
            # Rotate if needed (expand=True to swap width/height correctly on 90/270 deg)
            if rotate != 0:
                # Pillow rotation is counter-clockwise. For 90 degree clockwise, we pass -90.
                frame = frame.rotate(-rotate, expand=True)
                
            # Process image style
            if edge_detect:
                frame = frame.convert('L')
                frame = frame.filter(ImageFilter.FIND_EDGES)
                # FIND_EDGES makes edges white on black background. We want black edges on white background.
                from PIL import ImageOps
                frame = ImageOps.invert(frame)
                frame = frame.convert('1')
            elif threshold is not None:
                frame = frame.convert('L')
                frame = frame.point(lambda x: 0 if x < threshold else 255, '1')
            else:
                # Convert to 1-bit with dithering
                frame = frame.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
                
            frames.append(frame)
            
            # Skip frames if requested
            for _ in range(skip_frames + 1):
                gif.seek(gif.tell() + 1)
    except EOFError:
        pass

    if not frames:
        print("No frames found in the GIF.")
        sys.exit(1)

    # Generate C and H files
    h_file_content = f"#pragma once\n#include <lvgl.h>\n\n"
    c_file_content = f'#include "{output_name}.h"\n\n'
    
    for idx, frame in enumerate(frames):
        c_file_content += image_to_lvgl_1bit(frame, output_name, idx)
        h_file_content += f"extern const lv_img_dsc_t {output_name}_{idx};\n"
        
    # Array of all frames
    h_file_content += f"\nextern const lv_img_dsc_t* {output_name}_frames[{len(frames)}];\n"
    
    c_file_content += f"\nconst lv_img_dsc_t* {output_name}_frames[{len(frames)}] = {{\n"
    for idx in range(len(frames)):
        c_file_content += f"    &{output_name}_{idx},\n"
    c_file_content += "};\n"
    
    # Write to files
    os.makedirs(outdir, exist_ok=True)
    c_path = os.path.join(outdir, f"{output_name}.c")
    h_path = os.path.join(outdir, f"{output_name}.h")
    try:
        with open(c_path, "w") as f:
            f.write(c_file_content)
        with open(h_path, "w") as f:
            f.write(h_file_content)
    except Exception as e:
        print(f"Error writing output files: {e}")
        sys.exit(1)
        
    print(f"Successfully converted '{input_path}' into '{c_path}' and '{h_path}'")
    print(f"Total frames: {len(frames)}")
    if rotate != 0:
        print(f"Final dimensions (after {rotate} deg rotation): {frames[0].width}x{frames[0].height}")
    else:
        print(f"Final dimensions: {frames[0].width}x{frames[0].height}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert GIF to LVGL ZMK format")
    parser.add_argument("input_gif", help="Path to input GIF file")
    parser.add_argument("--name", default=None, help="Output C variable name (defaults to input filename)")
    parser.add_argument("--outdir", default=None, help="Output directory (defaults to animations/outputs)")
    parser.add_argument("--width", type=int, default=32, help="Target width BEFORE rotation (default: 32)")
    parser.add_argument("--height", type=int, default=32, help="Target height BEFORE rotation (default: 32)")
    parser.add_argument("--rotate", type=int, default=90, help="Rotation degrees (clockwise): 0, 90, 180, 270 (default: 90)")
    parser.add_argument("--threshold", type=int, default=128, help="Threshold level (0-255) for solid black outlines instead of dithering. (default: 128)")
    parser.add_argument("--dither", action="store_true", help="Use dithering instead of thresholding (best for gradients/photos)")
    parser.add_argument("--edge-detect", action="store_true", help="Apply edge detection to force an outline sketch effect")
    parser.add_argument("--scale", type=float, default=1.0, help="Scale factor to reduce output size (e.g. 0.5 for half size).")
    parser.add_argument("--skip-frames", type=int, default=0, help="Number of frames to skip between each kept frame (e.g. 1 to keep every other frame).")
    parser.add_argument("--resample", type=str, default="lanczos", choices=["lanczos", "nearest", "bicubic", "box", "bilinear", "hamming"], help="Resampling method to use for scaling (default: lanczos)")
    
    args = parser.parse_args()
    
    if args.name is None:
        base = os.path.basename(args.input_gif)
        name = os.path.splitext(base)[0]
        # Sanitize name for C variables
        name = "".join([c if c.isalnum() else "_" for c in name]).strip("_")
    else:
        name = args.name
        
    if args.outdir is None:
        outdir = os.path.join(os.path.dirname(script_dir), "animations", "outputs")
    else:
        outdir = args.outdir
        
    # Determine processing mode
    threshold = None if args.dither else args.threshold
    
    # Map resample string to PIL Resampling enum
    resampling_methods = {
        "lanczos": Image.Resampling.LANCZOS,
        "nearest": Image.Resampling.NEAREST,
        "bicubic": Image.Resampling.BICUBIC,
        "box": Image.Resampling.BOX,
        "bilinear": Image.Resampling.BILINEAR,
        "hamming": Image.Resampling.HAMMING
    }
    resample_method = resampling_methods[args.resample]
    
    # Apply scale
    target_w = int(args.width * args.scale)
    target_h = int(args.height * args.scale)
        
    process_gif(args.input_gif, name, target_w, target_h, args.rotate, outdir, threshold, args.edge_detect, args.skip_frames, resample_method)
