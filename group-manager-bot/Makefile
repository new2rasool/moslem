.PHONY: setup venv check test run lint

PY := python3
VENV := .venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

$(VENV):
	$(PY) -m venv $(VENV)
	$(PIP) install -q -e ".[dev]"

setup: $(VENV)        ## ساخت venv + نصب وابستگی‌های توسعه
	@echo "✅ آماده. حالا: make check / make test"

check:                ## بررسی سلامت اسکلت (فاز ۱) — بدون نیاز به تلگرام
	$(PY) -m bot.main --check

test:                 ## اجرای همهٔ تست‌ها
	$(PYTEST) -q

lint:
	$(VENV)/bin/ruff check bot tests
	$(VENV)/bin/mypy bot

run:                  ## اجرای واقعی ربات (نیازمند BOT_TOKEN)
	$(PY) -m bot.main --run
