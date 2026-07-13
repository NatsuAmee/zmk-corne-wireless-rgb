# ZMK GIF to LVGL Converter

This tool converts standard GIF animations into LVGL C array structures (`lv_img_dsc_t`) that can be used directly in custom ZMK display widgets.

## Requirements

The script requires Python and the Pillow library.

```bash
pip install Pillow
```

## Usage

By default, the script is configured to match the dimensions and orientation of the `nice!view` e-paper displays (which the Bongo Cat widget targets). 
It takes a standard landscape GIF (160x68 pixels), resizes it, rotates it 90 degrees clockwise (so it fits the physical portrait orientation of nice!view, which is 68x160), and converts it into a 1-bit monochrome C array.

```bash
./gif2zmk.py input_animation.gif
```

This will generate two files:
- `custom_anim.c` (Contains the raw image data and structs)
- `custom_anim.h` (Contains the header declarations)

### Advanced Usage

You can customize the output variable name, dimensions, and rotation:

```bash
./gif2zmk.py input_animation.gif --name my_cat --width 128 --height 32 --rotate 0
```

- `--name`: The base name for the C variables (default: `custom_anim`).
- `--width`: The target width of the image BEFORE rotation (default: 160).
- `--height`: The target height of the image BEFORE rotation (default: 68).
- `--rotate`: The rotation angle in degrees (default: 90). Use `0` if your display is mounted horizontally.

## How to use the output in ZMK

1. Move the generated `.c` and `.h` files into your custom ZMK widget directory (e.g., `boards/shields/corne/custom_widget/`).
2. Update your `CMakeLists.txt` to compile the `.c` file:
   ```cmake
   zephyr_library_sources(custom_anim.c)
   ```
3. Include the `.h` file in your widget's C code to access the array of frames:
   ```c
   #include "custom_anim.h"
   
   // custom_anim_frames is an array containing pointers to all frames
   // You can use them with lv_animimg_set_src()
   ```
