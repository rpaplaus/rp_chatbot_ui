# ============================================
# 🤖 Programmer's Multi-LLM Chatbot - Makefile
# ============================================

.PHONY: run install clean help

VENV := venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip

help: ## Show available commands
	@echo ""
	@echo "🤖 Programmer's Multi-LLM Chatbot"
	@echo "=================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36mmake %-12s\033[0m %s\n", $$1, $$2}'
	@echo ""

venv: ## Create virtual environment
	@if [ ! -d "$(VENV)" ]; then \
		echo "📦 Creating virtual environment..."; \
		python3 -m venv $(VENV); \
	fi

install: venv ## Install dependencies
	@echo "📦 Installing dependencies..."
	@$(PIP) install -r requirements.txt

run: venv ## Run the chatbot app
	@echo "🚀 Starting Programmer's Multi-LLM Chatbot..."
	@$(PYTHON) app.py

clean: ## Remove venv and cache files
	@echo "🧹 Cleaning up..."
	@rm -rf $(VENV) __pycache__ memory/*.json
	@echo "✅ Done!"
