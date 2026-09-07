.PHONY: install setup venv check test lint run

PY := python3
VENV := .venv
PYBIN := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:              ## نصب خودکار / automatic install (./install.sh)
	./install.sh

setup:                ## ساخت venv + ابزار توسعه / venv + dev tools
	./install.sh --dev

check:                ## بررسی سلامت (بدون تلگرام) / health check
	./run.sh --check

test:                 ## اجرای همهٔ تست‌ها / run all tests
	$(PYBIN) -m pytest -q

lint:
	$(VENV)/bin/ruff check bot tests
	$(VENV)/bin/mypy bot

run:                  ## اجرای واقعی (نیازمند .env تنظیم‌شده) / live run
	./run.sh --run
