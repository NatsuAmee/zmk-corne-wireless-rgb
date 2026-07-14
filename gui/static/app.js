document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            // Update active state
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            // Show target view
            const targetId = item.getAttribute('data-target');
            views.forEach(v => {
                if(v.id === targetId) {
                    v.classList.add('active');
                } else {
                    v.classList.remove('active');
                }
            });
            
            // Load specific view data if needed
            if (targetId === 'keymap-view' && !document.getElementById('keymap-editor').value) {
                loadKeymap();
            }
        });
    });

    // Toast Notification
    function showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = `toast show ${type}`;
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    // --- Settings View ---
    let currentConfig = {};
    const settingsContainer = document.getElementById('settings-container');
    const layoutContainer = document.getElementById('layout-container');

    async function loadConfig() {
        try {
            const res = await fetch('/api/config');
            if (!res.ok) throw new Error('Failed to load config');
            currentConfig = await res.json();
            renderSettings();
        } catch (e) {
            settingsContainer.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    }

    function renderSettings() {
        settingsContainer.innerHTML = '';
        layoutContainer.innerHTML = '';
        
        // Define some known categories
        const layoutWidgets = ['CONFIG_ZMK_WIDGET_WPM_STATUS', 'CONFIG_ZMK_WIDGET_BATTERY_STATUS_SHOW_PERCENTAGE', 'CONFIG_ZMK_WIDGET_LAYER_STATUS', 'CONFIG_ZMK_WIDGET_BATTERY_STATUS', 'CONFIG_ZMK_WIDGET_OUTPUT_STATUS', 'CONFIG_ZMK_DISPLAY', 'CONFIG_ZMK_DISPLAY_STATUS_SCREEN_CUSTOM'];
        
        for (const [key, value] of Object.entries(currentConfig)) {
            const isBool = value === 'y' || value === 'n';
            
            const card = document.createElement('div');
            card.className = 'setting-card';
            
            let inputHtml = '';
            if (isBool) {
                inputHtml = `
                    <label class="switch">
                        <input type="checkbox" id="config-${key}" ${value === 'y' ? 'checked' : ''}>
                        <span class="slider"></span>
                    </label>
                `;
            } else {
                // String or number input
                const displayVal = value.startsWith('"') ? value.replace(/"/g, '') : value;
                inputHtml = `<input type="text" id="config-${key}" class="setting-input" value="${displayVal}">`;
            }
            
            // Format nice name
            let niceName = key.replace('CONFIG_ZMK_', '').replace('CONFIG_', '').replace(/_/g, ' ');
            
            card.innerHTML = `
                <div class="setting-info">
                    <h3>${niceName}</h3>
                    <p>${key}</p>
                </div>
                <div class="setting-control">
                    ${inputHtml}
                </div>
            `;
            
            if (layoutWidgets.includes(key) || key.includes('WIDGET')) {
                layoutContainer.appendChild(card);
            } else {
                settingsContainer.appendChild(card);
            }
        }
    }

    async function saveConfig() {
        const newData = { ...currentConfig };
        document.querySelectorAll('input[id^="config-"]').forEach(input => {
            const key = input.id.replace('config-', '');
            if (input.type === 'checkbox') {
                newData[key] = input.checked ? 'y' : 'n';
            } else {
                const val = input.value;
                // Add quotes if original had quotes, simplistic heuristic
                if (currentConfig[key] && currentConfig[key].startsWith('"') && !val.startsWith('"')) {
                    newData[key] = `"${val}"`;
                } else {
                    newData[key] = val;
                }
            }
        });

        try {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newData)
            });
            if (res.ok) {
                showToast('Settings saved successfully');
                currentConfig = newData;
            } else {
                throw new Error('Save failed');
            }
        } catch (e) {
            showToast(e.message, 'error');
        }
    }

    document.getElementById('save-settings').addEventListener('click', saveConfig);
    document.getElementById('save-layout').addEventListener('click', saveConfig);


    // --- Keymap View ---
    const keymapEditor = document.getElementById('keymap-editor');
    const keymapPreview = document.getElementById('keymap-preview');

    async function loadKeymap() {
        try {
            const res = await fetch('/api/keymap');
            if (res.ok) {
                const data = await res.json();
                keymapEditor.value = data.content;
            }
        } catch (e) {
            console.error(e);
        }
    }

    document.getElementById('save-keymap').addEventListener('click', async () => {
        // Save first
        const content = keymapEditor.value;
        try {
            let res = await fetch('/api/keymap', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content })
            });
            
            if (!res.ok) throw new Error('Failed to save keymap');
            
            // Request preview
            keymapPreview.innerHTML = '<div class="empty-state">Generating preview...</div>';
            res = await fetch('/api/keymap/preview', { method: 'POST' });
            
            if (res.ok) {
                const data = await res.json();
                if (data.svg) {
                    keymapPreview.innerHTML = data.svg;
                } else {
                    throw new Error(data.error || 'Preview generation failed');
                }
            } else {
                const data = await res.json();
                throw new Error(data.error || 'Preview failed');
            }
            showToast('Keymap saved and preview updated');
        } catch (e) {
            showToast(e.message, 'error');
            keymapPreview.innerHTML = `<div class="empty-state" style="color: #ef4444;">${e.message}</div>`;
        }
    });

    // --- Animations View ---
    document.getElementById('generate-anim').addEventListener('click', async () => {
        const name = document.getElementById('anim-name').value;
        const gif = document.getElementById('anim-path').value;
        const duration = document.getElementById('anim-duration').value;
        const rotate = document.getElementById('anim-rotate').value;
        const scale = document.getElementById('anim-scale').value;
        const skipFrames = document.getElementById('anim-skip-frames').value;
        const statusEl = document.getElementById('anim-status') || document.createElement('div'); // Handle if missing

        if (!name || !gif) {
            statusEl.className = 'status-msg error';
            statusEl.textContent = 'Name and GIF path are required.';
            return;
        }

        statusEl.className = 'status-msg';
        statusEl.textContent = 'Generating animation C code... this may take a moment.';

        try {
            const res = await fetch('/api/animations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, gif, duration, rotate, scale, skipFrames })
            });

            if (res.ok) {
                statusEl.className = 'status-msg success';
                statusEl.textContent = 'Animation added successfully! Enable it in OLED Layout settings.';
                // Reload config to get the new widget toggle
                loadConfig();
            } else {
                const data = await res.json();
                throw new Error(data.error || 'Generation failed');
            }
        } catch (e) {
            statusEl.className = 'status-msg error';
            statusEl.textContent = `Error: ${e.message}`;
        }
    });

    // Initial load
    loadConfig();
});
