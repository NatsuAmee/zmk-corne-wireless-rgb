import os
import subprocess
import json
from flask import Flask, request, jsonify, render_template

app = Flask(__name__, static_folder='static', template_folder='templates')
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'config', 'corne.conf')
KEYMAP_FILE = os.path.join(PROJECT_ROOT, 'config', 'corne.keymap')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    if not os.path.exists(CONFIG_FILE):
        return jsonify({"error": "corne.conf not found"}), 404
        
    config_dict = {}
    with open(CONFIG_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('CONFIG_') and '=' in line:
                key, val = line.split('=', 1)
                config_dict[key] = val
    return jsonify(config_dict)

@app.route('/api/config', methods=['POST'])
def save_config():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    if not os.path.exists(CONFIG_FILE):
        return jsonify({"error": "corne.conf not found"}), 404
        
    lines = []
    with open(CONFIG_FILE, 'r') as f:
        lines = f.readlines()
        
    # Update lines
    for key, val in data.items():
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}=") or line.startswith(f"#{key}="):
                lines[i] = f"{key}={val}\n"
                found = True
                break
        if not found:
            lines.append(f"{key}={val}\n")
            
    with open(CONFIG_FILE, 'w') as f:
        f.writelines(lines)
        
    return jsonify({"success": True})

@app.route('/api/keymap', methods=['GET'])
def get_keymap():
    if not os.path.exists(KEYMAP_FILE):
        return jsonify({"error": "corne.keymap not found"}), 404
        
    with open(KEYMAP_FILE, 'r') as f:
        content = f.read()
    return jsonify({"content": content})

@app.route('/api/keymap', methods=['POST'])
def save_keymap():
    data = request.json
    content = data.get('content')
    if not content:
        return jsonify({"error": "No content provided"}), 400
        
    with open(KEYMAP_FILE, 'w') as f:
        f.write(content)
        
    return jsonify({"success": True})

@app.route('/api/keymap/preview', methods=['POST'])
def generate_preview():
    # Run keymap parse and draw
    try:
        # keymap parse -z config/corne.keymap -c config/corne.conf > keymap-drawer/corne.yaml
        subprocess.run(['.venv/bin/keymap', 'parse', '-z', KEYMAP_FILE, '-c', 'config/config_keymap-drawer.yaml'], 
                       cwd=PROJECT_ROOT, check=True, capture_output=True)
        # keymap draw keymap-drawer/corne.yaml > keymap-drawer/corne.svg
        subprocess.run(['.venv/bin/keymap', 'draw', 'keymap-drawer/corne.yaml', '-c', 'config/config_keymap-drawer.yaml'], 
                       cwd=PROJECT_ROOT, check=True, capture_output=True, stdout=open(os.path.join(PROJECT_ROOT, 'keymap-drawer', 'corne.svg'), 'w'))
        
        # Read the generated SVG
        svg_path = os.path.join(PROJECT_ROOT, 'keymap-drawer', 'corne.svg')
        with open(svg_path, 'r') as f:
            svg_content = f.read()
            
        return jsonify({"svg": svg_content})
    except subprocess.CalledProcessError as e:
        return jsonify({"error": str(e), "stderr": e.stderr.decode('utf-8') if e.stderr else ''}), 500
    except Exception as e:
         return jsonify({"error": str(e)}), 500

@app.route('/api/animations', methods=['POST'])
def add_animation():
    data = request.json
    name = data.get('name')
    gif_path = data.get('gif')
    duration = data.get('duration', '960')
    rotate = data.get('rotate', '90')
    scale = data.get('scale', '1.0')
    skip_frames = data.get('skipFrames', '0')
    
    if not name or not gif_path:
        return jsonify({"error": "Name and GIF path are required"}), 400
        
    try:
        # Check if gif exists
        if not os.path.exists(gif_path):
             return jsonify({"error": "GIF file not found"}), 404
             
        subprocess.run(['.venv/bin/python', 'scripts/add_animation.py', 
                        '--name', name, 
                        '--gif', gif_path, 
                        '--duration', str(duration), 
                        '--rotate', str(rotate),
                        '--scale', str(scale),
                        '--skip-frames', str(skip_frames)], 
                       cwd=PROJECT_ROOT, check=True, capture_output=True)
        return jsonify({"success": True})
    except subprocess.CalledProcessError as e:
        return jsonify({"error": str(e), "stderr": e.stderr.decode('utf-8') if e.stderr else ''}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
