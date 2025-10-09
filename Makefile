.PHONY: lint test run-paper run-live backtest

lint:
	python -m compileall src

test:
	pytest -q || true

run-paper:
	python production_main.py --mode paper

run-live:
	python production_main.py --mode live

backtest:
	python backtest.py
