import os
import shutil

print("🧹 Cleaning up previous attempts and cache files...")
# 1. Delete the incomplete cookiecutter folder
if os.path.exists("multi_agent_cookiecutter"):
    shutil.rmtree("multi_agent_cookiecutter")

# 2. Delete lock files that shouldn't be in a template
if os.path.exists("uv.lock"):
    os.remove("uv.lock")

# 3. Delete all __pycache__ directories
for root, dirs, files in os.walk(".", topdown=False):
    for name in dirs:
        if name == "__pycache__":
            shutil.rmtree(os.path.join(root, name))

print("🏗️ Creating clean template structure...")
base_dir = "multi_agent_cookiecutter"
slug_dir = os.path.join(base_dir, "{{cookiecutter.project_slug}}")
os.makedirs(slug_dir, exist_ok=True)

# 4. Safely move ALL your existing files into the slug directory
exclude = [base_dir, "convert.py", ".git", ".DS_Store"]
for item in os.listdir("."):
    if item not in exclude:
        print(f"  -> Moving {item} to template...")
        shutil.move(item, slug_dir)

print("📝 Generating cookiecutter.json...")
cookiecutter_json = """{
  "project_name": "Multi Agent Platform",
  "project_slug": "{{ cookiecutter.project_name.lower().replace(' ', '_').replace('-', '_') }}",
  "author_name": "Arif",
  "description": "Real-time, offline, multi-agent architecture.",
  "python_version": "3.11"
}"""
with open(os.path.join(base_dir, "cookiecutter.json"), "w") as f:
    f.write(cookiecutter_json)

print("💉 Injecting Cookiecutter variables into your code...")
def replace_in_file(filepath, replacements):
    full_path = os.path.join(slug_dir, filepath)
    if not os.path.exists(full_path):
        return
        
    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

# Update pyproject.toml
replace_in_file("pyproject.toml", [
    ('name = "voice-ai-agent"', 'name = "{{cookiecutter.project_slug}}"'),
    ('name = "voice_ai_agent"', 'name = "{{cookiecutter.project_slug}}"'),
    ('description = "Real-time, offline, multi-agent voice AI architecture"', 'description = "{{cookiecutter.description}}"')
])

# Update docker-compose.yml
replace_in_file("docker-compose.yml", [
    ('voice_ai_api', '{{cookiecutter.project_slug}}_api'),
    ('voice_ai_docs', '{{cookiecutter.project_slug}}_docs'),
    ('voice_ai_qdrant', '{{cookiecutter.project_slug}}_qdrant'),
    ('voice_ai_ollama', '{{cookiecutter.project_slug}}_ollama'),
])

# Update config.py
replace_in_file("src/backend/core/config.py", [
    ('api_title: str = "Voice AI Agent API"', 'api_title: str = "{{cookiecutter.project_name}} API"'),
    ('qdrant_collection: str = "voice_ai_docs"', 'qdrant_collection: str = "{{cookiecutter.project_slug}}_docs"')
])

print("✅ Success! Your project is now perfectly wrapped inside 'multi_agent_cookiecutter'.")