# Telemt Stack Ansible

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Automated deployment of **Telemt (MTProto proxy) + Panel + Bot** via Ansible & Docker Compose. Idempotent, secure, and production-ready.

## Content
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [What's Created on Server](#whats-created-on-server)
- [Components](#components)
- [Upstream](#upstream)
- [Project Structure](#project-structure)
- [Security Notes](#security-notes)
- [Cleanup](#cleanup)
- [License](#license)

## Features
- **Modular deployment**: Deploy only the components you need (core + optional panel/bot)
- **Flexible authentication**: Set panel password as plain text (auto-hashed) or provide pre-hashed bcrypt
- **Auto-generated secrets**: JWT, password hashes, and user secrets created on first run if not filled manually
- **Docker auto-install**: Ansible automatically installs Docker on bare Debian/Ubuntu servers

## Requirements

**Control Node** (where you run Ansible):
- Linux/macOS with Python 3.9+
- `git`, `make`, `python3-venv`
- SSH key for server access

**Target Server**:
- Debian 11/12/13 or Ubuntu 20.04+
- SSH key-based access
- `sudo` privileges for the user

## Installation

1. Clone & enter directory:
```bash
git clone https://github.com/sandvagg/telemt-stack-ansible.git
cd telemt-stack-ansible
```

2. Setup environment & install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r ansible-requirements.txt
ansible-galaxy collection install -r ansible-collections-requirements.yml
```

3. Initialize configuration files:
```bash
make init
```

## Configuration

Edit three files to match your infrastructure:

### `inventory/hosts.ini`
```ini
[telemt_servers]
my-vps ansible_host=123.123.123.123 ansible_user=vps_user ansible_ssh_private_key_file=~/.ssh/id_ed25519
# or with sudo password
my-vps ansible_host=123.123.123.123 ansible_user=vps_user ansible_become_password=your_sudo_password

[telemt_servers:vars]
ansible_become=yes
ansible_python_interpreter=auto_silent
```

### `group_vars/all.yml`
```yaml
telemt_public_host: "your.server.ip"    # ← IP or domain for tg:// links
telemt_tls_domain: "fake.domain.com"    # ← domain for TLS masking (not a real domain!)
deploy_panel: true                      # ← set to false if you don't need the web panel
deploy_bot: false                       # ← set to true if you need the Telegram bot

# API Security: Whitelist only Docker internal network
telemt_api_whitelist:
  - "172.16.0.0/12"   # Docker default pool (containers can access API)
  # - "127.0.0.1/32"  # Uncomment for localhost debug access from host
```

### `secrets/secrets.yml`
```yaml
# === Panel Authentication (Choose ONE method) ===

# Method A: Plain password (recommended)
# The hash will be auto-generated on first deploy
panel_password: "MySecurePass123"
panel_password_hash: ""  # Leave empty for auto-generation

# Method B: Pre-hashed password (advanced)
# panel_password: ""
# panel_password_hash: "$2b$10$..."  # bcrypt, rounds=10

# === Other Secrets ===
bot_token: "123456789:AAH..."           # from @BotFather
bot_admin_ids:                          # your Telegram UID (as integers)
  - 123456789

# Auto-generated fields (filled on first run if empty):
panel_jwt_secret: ""
telemt_users:
  user1: ""
# Other fields (panel_jwt_secret, telemt_users.*) are auto-generated on first run if not filled manually
```

## Usage

### Check & Deploy
```bash
make check    # Ansible syntax check only (safe, no remote changes)
make deploy   # Full deployment based on all.yml settings
```

### Quick Combinations (temporarily override `all.yml`)
```bash
make deploy-minimal     # Only Telemt (proxy core)
make deploy-with-panel  # Telemt + Panel
make deploy-with-bot    # Telemt + Bot
```

## What's Created on Server

Running `make deploy` provisions the following on the target host:

### Directory Structure
```bash
/opt/telemt-stack/                 # telemt_base_dir
├── docker-compose.yml             # Generated Compose file
├── telemt_config/
│   └── telemt.toml                # Proxy core configuration
├── panel-config/
│   └── config.toml                # Panel configuration (if deployed)
└── bot/
    ├── Dockerfile
    ├── .env                       # Bot environment variables (mode 0600)
    ├── requirements.txt
    ├── telemt-bot.py              # Telegram bot source code
    └── logs/                      # Bot logs directory
```

### 🐳 Docker Resources
| Resource | Name | Description |
|----------|------|-------------|
| **Network** | `telemt-net` | Isolated `bridge` network for container communication |
| **Container** | `telemt` | MTProto proxy core (always deployed) |
| **Container** | `telemt-panel` | Web management interface (if `deploy_panel: true`) |
| **Container** | `telemt-bot` | Telegram management bot (if `deploy_bot: true`) |

### ⚙️ System Changes
- **Docker Engine & Compose Plugin**: Installed automatically (Debian/Ubuntu only)
- **UFW Firewall**: Port `{{ telemt_public_port }}/tcp` (default `443`) opened if UFW is active
- **File Permissions**: Configs `0644`, `.env` & secrets `0600`
- **Container Hardening**: `cap_drop: ALL`, `read_only: true`, `no-new-privileges: true`, `tmpfs` for `/tmp`

> All operations are idempotent. Re-running `make deploy` updates only changed files and restarts affected services.

## Components

| Flag | Component | Description |
|------|-----------|-------------|
| `deploy_panel` | Web Panel | Installs `telemt-panel` (default: `true`) |
| `deploy_bot`   | Telegram Bot | Installs `telemt-bot` (default: `false`) |

> **The `telemt` core is always installed.**

## Upstream

This project orchestrates the following components:

| Component | Repository | Docker Image |
|-----------|------------|--------------|
| **Telemt** (Proxy Core) | [whn0thacked/telemt-docker](https://github.com/whn0thacked/telemt-docker) | `whn0thacked/telemt-docker:3.3.28` |
| **Panel** (Web UI) | [amirotin/telemt_panel](https://github.com/amirotin/telemt_panel) | `ghcr.io/amirotin/telemt_panel:0.5.2` |
| **Bot** (Telegram) | _Local_ (`bot/telemt-bot.py`) | Built from `bot/Dockerfile` |

## Project Structure

```
telemt-stack-ansible/
├── playbooks/deploy.yml          # Main playbook (2 plays: secrets → deploy)
├── templates/                    # Jinja2 configuration templates
│   ├── docker-compose.yml.j2
│   ├── telemt.toml.j2
│   ├── panel-config.toml.j2
│   └── bot-env.j2
├── group_vars/
│   └── all.yml.example           # Public variables (IPs, ports, flags)
├── secrets/
│   ├── secrets.yml.example       # Secrets template (with plain+hash docs)
│   ├── panel-credentials.txt     # Contains plain password for panel (optionally)
│   └── secrets.yml               # Auto-filled on first run if not filled manually
├── bot/                          # Local bot source code
│   ├── Dockerfile
│   ├── requirements.txt
│   └── telemt-bot.py
├── inventory/
│   └── hosts.ini.example         # Inventory template
├── requirements.yml              # Ansible collections
├── requirements-ansible.txt      # Python dependencies
├── Makefile                      # Convenient commands
├── ansible.cfg                   # Ansible settings
└── README.md
```

## Security Notes

### API Access Control
The Telemt API is protected by two layers:
1. **Network isolation**: API port bound to `127.0.0.1` on host; containers communicate via Docker network.
2. **Application whitelist**: `telemt_api_whitelist` restricts access to `172.16.0.0/12` (Docker pool).

> To access API from host for debugging, add `"127.0.0.1/32"` to whitelist and use `curl http://127.0.0.1:9091`.

### Access to Service Files
By default, only the `telemt` user can read service directories. To access logs/configs without `sudo`:
```bash
sudo usermod -aG telemt $USER # re-login after that
```

### Password Management
- If you set `panel_password` (plain), the hash is auto-generated and stored in `panel_password_hash`.
- Changing `panel_password` triggers hash regeneration on next deploy.
- If only `panel_password_hash` is set (no plain), the system operates in "hash-only" mode

## Cleanup

To completely remove the stack from the target server, run the following commands (or execute via SSH):

```bash
# 1. Stop & remove containers and networks
ssh user@host 'docker compose -f /opt/telemt-stack/docker-compose.yml down'

# 2. Clean up unused images, containers, and volumes (optional)
ssh user@host 'docker system prune -af --volumes'

# 3. Remove the project directory
ssh user@host 'sudo rm -rf /opt/telemt-stack'

# 4. (Optional) Remove Docker if it's no longer needed
ssh user@host 'sudo apt purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin && sudo apt autoremove -y'
```

> **Warning:** This operation is irreversible. All proxy users, logs, and configurations will be permanently deleted. Ensure you have backups if needed.

## License

The project is distributed under the **MIT** license:

```text

Copyright (c) 2026 sandvagg

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
