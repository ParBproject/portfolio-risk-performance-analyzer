PY ?= python
.PHONY: install data db results sql test lint app all
install: ; $(PY) -m pip install -e ".[dev]"
data: ; $(PY) -m prpa.ingest        # re-download (changes hashes; normally not needed)
db: ; $(PY) -m prpa.db
results: ; $(PY) -m prpa.analysis && $(PY) -m prpa.stage3 && $(PY) -m prpa.stage4
lint: ; ruff check . && ruff format --check .
test: ; pytest -q
app: ; streamlit run app/streamlit_app.py
sql: ; $(PY) scripts/run_queries.py
all: results sql lint test
