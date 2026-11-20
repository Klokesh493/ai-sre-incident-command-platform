PYTHON ?= python3
.PHONY: test replay check serve
test:
	$(PYTHON) -m pytest -q
replay:
	$(PYTHON) tools/replay.py
check: test replay
	$(PYTHON) -m ruff check .
	$(PYTHON) -m bandit -q -ll -ii -r ops_platform tools
serve:
	$(PYTHON) -m uvicorn ops_platform.service:create_app --factory --host 127.0.0.1 --port 8000
