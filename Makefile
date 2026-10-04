PYTHON ?= python

.PHONY: test audit export analyze figures reproduce reproduce-fast validate clean

test:
	$(PYTHON) -m pytest -q

audit:
	$(PYTHON) scripts/audit_text_deltas.py
	$(PYTHON) scripts/audit_suggestion_episodes.py
	$(PYTHON) scripts/audit_provenance.py
	$(PYTHON) scripts/audit_metrics.py

export:
	$(PYTHON) scripts/export_metrics.py
	$(PYTHON) scripts/export_target_behavior.py

analyze:
	$(PYTHON) -m agencytrace.analysis

figures:
	$(PYTHON) -m agencytrace.figures

reproduce:
	$(PYTHON) scripts/reproduce_all.py

reproduce-fast:
	$(PYTHON) scripts/reproduce_all.py --skip-audits

validate:
	$(PYTHON) scripts/validate_release.py

clean:
	$(PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['data/processed', 'data/analysis', '.pytest_cache']]"