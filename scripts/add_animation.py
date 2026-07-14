#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import re
from PIL import Image

def get_frame_count(gif_path):
    try:
        gif = Image.open(gif_path)
        return gif.n_frames
    except Exception as e:
        print(f"Error opening GIF to count frames: {e}")
        return 0

def run_gif2zmk(name, gif_path, rotate):
    print(f"Running gif2zmk.py for '{name}'...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gif2zmk_path = os.path.join(script_dir, "gif2zmk.py")
    outdir = os.path.join(script_dir, "..", "boards", "shields", "nice_oled", "assets")
    
    cmd = [
        sys.executable,
        gif2zmk_path,
        gif_path,
        "--name", name,
        "--rotate", str(rotate),
        "--outdir", outdir
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Error running gif2zmk.py:")
        print(result.stderr)
        sys.exit(1)
    
    print(result.stdout)
    return get_frame_count(gif_path)

def inject_kconfig(name, duration):
    print(f"Injecting into Kconfig.defconfig...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    kconfig_path = os.path.join(script_dir, "..", "boards", "shields", "nice_oled", "Kconfig.defconfig")
    
    with open(kconfig_path, "r") as f:
        content = f.read()
        
    config_name = f"CONFIG_NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_{name.upper()}"
    
    if config_name in content:
        print(f"{config_name} already exists in Kconfig.defconfig. Skipping.")
        return
        
    # Inject boolean flag
    injection = f"""
config {config_name}
    bool "Enable {name} animation on peripheral"
    default n
"""
    # Insert right before CONFIG_NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_HEAD
    content = content.replace(
        "config NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_HEAD",
        f"{injection.strip()}\n\nconfig NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_HEAD"
    )
    
    # Inject default duration
    dur_injection = f"    default {duration} if {config_name}"
    content = content.replace(
        "    default 960 if NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_GEM",
        f"{dur_injection}\n    default 960 if NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_GEM"
    )
    
    with open(kconfig_path, "w") as f:
        f.write(content)
    print("Done Kconfig.defconfig.")

def inject_cmake(name):
    print(f"Injecting into CMakeLists.txt...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cmake_path = os.path.join(script_dir, "..", "boards", "shields", "nice_oled", "CMakeLists.txt")
    
    with open(cmake_path, "r") as f:
        content = f.read()
        
    config_name = f"CONFIG_NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_{name.upper()}"
    
    if f"{config_name} app PRIVATE assets/{name}.c" in content:
        print(f"CMake rule for {name} already exists. Skipping.")
        return
        
    rule = f"      target_sources_ifdef({config_name} app PRIVATE assets/{name}.c)"
    content = content.replace(
        "      target_sources_ifdef(CONFIG_NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_CAT app PRIVATE assets/cat.c)",
        f"      target_sources_ifdef(CONFIG_NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_CAT app PRIVATE assets/cat.c)\n{rule}"
    )
    
    with open(cmake_path, "w") as f:
        f.write(content)
    print("Done CMakeLists.txt.")

def inject_animation_c(name, frames):
    print(f"Injecting into animation.c...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    anim_c_path = os.path.join(script_dir, "..", "boards", "shields", "nice_oled", "widgets", "animation.c")
    
    with open(anim_c_path, "r") as f:
        content = f.read()
        
    config_name = f"CONFIG_NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_{name.upper()}"
    
    if config_name in content:
        print(f"Logic for {name} already exists in animation.c. Skipping.")
        return
        
    # Generate declarations
    decls = f"#elif IS_ENABLED({config_name})\n"
    for i in range(frames):
        decls += f"LV_IMG_DECLARE({name}_{i});\n"
        
    array_elems = ", ".join([f"&{name}_{i}" for i in range(frames)])
    decls += f"\nconst lv_img_dsc_t *{name}_imgs[] = {{{array_elems}}};\n"
    
    content = content.replace(
        "#elif IS_ENABLED(CONFIG_NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_SPACEMAN)",
        f"{decls}\n#elif IS_ENABLED(CONFIG_NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_SPACEMAN)"
    )
    
    # Inject set_src
    src_logic = f"""#elif IS_ENABLED({config_name})
    lv_animimg_set_src(art, (const void **){name}_imgs, {frames});"""
    
    content = content.replace(
        "#elif IS_ENABLED(CONFIG_NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_SPACEMAN)\n    lv_animimg_set_src(art, (const void **)spaceman_imgs, 20);",
        f"{src_logic}\n#elif IS_ENABLED(CONFIG_NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_SPACEMAN)\n    lv_animimg_set_src(art, (const void **)spaceman_imgs, 20);"
    )
    
    with open(anim_c_path, "w") as f:
        f.write(content)
    print("Done animation.c.")

def main():
    parser = argparse.ArgumentParser(description="Add a new animation to zmk-nice-oled")
    parser.add_argument("--name", required=True, help="Internal name of the animation (e.g. pikachu, dudu)")
    parser.add_argument("--gif", required=True, help="Path to the source GIF")
    parser.add_argument("--duration", type=int, default=960, help="Duration of the animation in ms (default: 960)")
    parser.add_argument("--rotate", type=int, default=90, help="Rotation degrees (default: 90)")
    
    args = parser.parse_args()
    
    # Sanitize name
    name = args.name.lower().replace(" ", "_")
    
    if not os.path.exists(args.gif):
        print(f"Error: GIF file '{args.gif}' does not exist.")
        sys.exit(1)
        
    frames = run_gif2zmk(name, args.gif, args.rotate)
    if frames == 0:
        print("Failed to determine frame count.")
        sys.exit(1)
        
    inject_kconfig(name, args.duration)
    inject_cmake(name)
    inject_animation_c(name, frames)
    
    print("\n--- Success! ---")
    print(f"Animation '{name}' added. To enable it, add the following to your config:")
    print(f"CONFIG_NICE_OLED_WIDGET_ANIMATION_PERIPHERAL_{name.upper()}=y")

if __name__ == "__main__":
    main()
