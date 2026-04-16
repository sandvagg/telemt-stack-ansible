.PHONY: init check diff deploy deploy-minimal deploy-with-panel deploy-with-bot logs clean help

# Settings
INVENTORY ?= inventory/hosts.ini
PLAYBOOK  := playbooks/deploy.yml
VERBOSE   ?=

# Проверка venv
ansible-playbook:
	@test -f $(ansible-playbook) || { \
		echo "Virtual environment not found."; \
		echo "Install: python3 -m venv .venv && source .venv/bin/activate && pip install ansible-core passlib bcrypt"; \
		echo "Install collection: ansible-galaxy collection install community.docker"; \
		exit 1; \
	}

help:
	@echo "Telemt Stack Ansible — proxy stack management"
	@echo ""
	@echo "Usage:"
	@echo "  make init     			# Create secrets.yml from example (local)"
	@echo "  make check    			# Check syntax"
	@echo "  make diff					# Showing config diffs (read-only)"
	@echo "  make deploy   			# Deploy using all.yml settings (main command)"
	@echo "  deploy-minimal    	# Telemt only (temporary override)"
	@echo "  deploy-with-panel 	# Telemt + Panel (temporary override)"
	@echo "  deploy-with-bot   	# Telemt + Bot (temporary override)"
	@echo "  make logs     			# Show container logs (requires SSH)"
	@echo "  make clean    			# Delete generated local secrets (does not affect server)"
	@echo "	 make clean all			# Delete secrets.yml and all.yml (does not affect server)"

init:
	@cp -n secrets/secrets.yml.example secrets/secrets.yml 2>/dev/null || true
	@chmod 600 secrets/secrets.yml
	@cp -n inventory/hosts.ini.example inventory/hosts.ini 2>/dev/null || true
	@cp -n group_vars/all.yml.example group_vars/all.yml 2>/dev/null || true
	@echo "secrets/secrets.yml created. Edit and run 'make deploy'"

check:
	ansible-playbook $(PLAYBOOK) -i $(INVENTORY) --syntax-check

diff:
	ansible-playbook $(PLAYBOOK) -i $(INVENTORY) --diff

deploy:
	@echo "Deploy using all.yml settings"
	ansible-playbook $(PLAYBOOK) -i $(INVENTORY) $(VERBOSE)

deploy-minimal:
	@echo "Deploy: Telemt only (no panel or bot)"
	ansible-playbook $(PLAYBOOK) -i $(INVENTORY) -e '{"deploy_panel": false, "deploy_bot": false}' $(VERBOSE)

deploy-with-panel:
	@echo "Deploy: Telemt + Panel"
	ansible-playbook $(PLAYBOOK) -i $(INVENTORY) -e '{"deploy_panel": true, "deploy_bot": false}' $(VERBOSE)

deploy-with-bot:
	@echo "Deploy: Telemt + Bot"
	ansible-playbook $(PLAYBOOK) -i $(INVENTORY) -e '{"deploy_panel": false, "deploy_bot": true}' $(VERBOSE)

logs:
	ansible telemt_servers -a "docker compose -f {{ telemt_base_dir }}/docker-compose.yml logs -f"

clean:
	@rm -f secrets/secrets.yml secrets/panel-credentials.txt
	@echo "Local secrets have been deleted."

clean-all:
	@rm -f secrets/secrets.yml
	@rm -f all.yml
	@echo "Secrets.yml and all.yml have been deleted"
