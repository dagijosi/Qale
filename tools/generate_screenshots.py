import json
import os
import shutil
import subprocess
import time

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_HTML = os.path.join(BASE_DIR, "web_ui", "index.html")
HUD_HTML = os.path.join(BASE_DIR, "web_ui", "hud.html")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "assets", "screenshots")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config_data = json.load(f)

with open(INDEX_HTML, "r", encoding="utf-8") as f:
    index_html_content = f.read()

with open(HUD_HTML, "r", encoding="utf-8") as f:
    hud_html_content = f.read()

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Generate screenshots for tabs:
# 1. general
# 2. ai (AI & Contexts)
# 3. vocab (Vocabulary & Presets)
# 4. playground (Voice Syntax Playground)

tabs = [
    ("general", "dashboard_general.png", 1160, 780, None),
    ("ai", "ai_context_profiles.png", 1160, 780, None),
    ("vocab", "vocabulary_presets.png", 1160, 780, None),
    ("playground", "syntax_playground.png", 1160, 780, """
        setTimeout(() => {
            const input = document.getElementById('playground-input');
            const prof = document.getElementById('playground-profile');
            const output = document.getElementById('playground-output');
            const meta = document.getElementById('playground-meta');
            if (prof) prof.value = 'ts';
            if (input) input.value = 'const user equals await prisma dot user dot find unique open paren curly where colon curly id close curly close curly close paren semicolon';
            if (output) output.innerText = 'const user = await prisma.user.findUnique({ where: { id } });';
            if (meta) meta.innerHTML = '<span class="badge-tag">TypeScript / React</span> Inferred Profile: TS &middot; Pipeline Latency: 12.4ms &middot; Zero Network Egress';
        }, 150);
    """)
]

for tab_id, filename, width, height, custom_js in tabs:
    js_inject = f"""
    <script>
      window.pywebview = {{
        api: {{
          get_config: async () => ({json.dumps(config_data)}),
          get_audio_devices: async () => [
            {{ index: 0, name: "Microphone Array (Realtek(R) Audio)" }},
            {{ index: 1, name: "External Studio Mic (USB)" }}
          ],
          test_parse: async (input, prof) => ({{ content: input, profile: prof, latency_ms: 12.4 }}),
          get_history: async () => []
        }}
      }};
      window.addEventListener('DOMContentLoaded', () => {{
        if (typeof loadConfigToUI === 'function') {{
          loadConfigToUI({json.dumps(config_data)});
        }}
        if (typeof populateDevices === 'function') {{
          populateDevices([
            {{ index: 0, name: "Microphone Array (Realtek(R) Audio)" }},
            {{ index: 1, name: "External Studio Mic (USB)" }}
          ]);
        }}
        if (typeof switchTab === 'function') {{
          switchTab('{tab_id}');
        }}
        {custom_js or ''}
      }});
    </script>
    """
    modified_html = index_html_content.replace("</head>", js_inject + "\n</head>")
    temp_html_path = os.path.join(OUTPUT_DIR, f"temp_{tab_id}.html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(modified_html)

    out_png = os.path.join(OUTPUT_DIR, filename)
    file_uri = "file:///" + temp_html_path.replace("\\", "/")
    cmd = [
        EDGE_PATH,
        "--headless=new",
        "--disable-gpu",
        f"--window-size={width},{height}",
        f"--screenshot={out_png}",
        file_uri
    ]
    subprocess.run(cmd, check=True)
    if os.path.exists(temp_html_path):
        os.remove(temp_html_path)
    print(f"Captured {filename} ({width}x{height})")

# Also generate Floating HUD screenshot
hud_js_inject = """
<script>
  window.addEventListener('DOMContentLoaded', () => {
    const card = document.getElementById('hud-card');
    const statusText = document.getElementById('status-text');
    const badge = document.getElementById('latency-badge');
    const waves = document.getElementById('sound-waves');
    if (statusText) statusText.innerHTML = '<span style="color:#10B981;font-weight:600;">INJECTED</span> &middot; VS Code &middot; <span style="color:#FAFAFA;">const user = await prisma...</span>';
    if (badge) {
      badge.innerText = '178ms';
      badge.style.display = 'inline-block';
    }
    if (waves) {
      waves.style.display = 'flex';
      Array.from(waves.children).forEach((bar, i) => {
        bar.style.height = (8 + (i % 3) * 6) + 'px';
      });
    }
  });
</script>
"""
modified_hud = hud_html_content.replace("</head>", hud_js_inject + "\n</head>")
temp_hud_path = os.path.join(OUTPUT_DIR, "temp_hud.html")
with open(temp_hud_path, "w", encoding="utf-8") as f:
    f.write(modified_hud)

out_hud_png = os.path.join(OUTPUT_DIR, "floating_hud.png")
file_uri_hud = "file:///" + temp_hud_path.replace("\\", "/")
cmd_hud = [
    EDGE_PATH,
    "--headless=new",
    "--disable-gpu",
    "--window-size=540,160",
    f"--screenshot={out_hud_png}",
    file_uri_hud
]
subprocess.run(cmd_hud, check=True)
if os.path.exists(temp_hud_path):
    os.remove(temp_hud_path)
print("Captured floating_hud.png (540x160)")

# Clean up temporary test screenshot in root if exists
if os.path.exists(os.path.join(BASE_DIR, "screenshot.png")):
    os.remove(os.path.join(BASE_DIR, "screenshot.png"))

# Copy to brain artifact directory for previewing
ARTIFACT_DIR = r"C:\Users\HP Victus\.gemini\antigravity\brain\ef8c6352-2b2e-48ec-894d-7c26d9409a23"
if os.path.exists(ARTIFACT_DIR):
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith(".png"):
            shutil.copy2(os.path.join(OUTPUT_DIR, f), os.path.join(ARTIFACT_DIR, f))

print("All screenshots generated and synced successfully!")
