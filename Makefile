PY ?= python3

.PHONY: db seed reset check check-db check-ingest check-profile check-plan check-chat spend help

help:
	@echo "make db       - apply schema.sql to palate.db"
	@echo "make seed     - load seed/seed.sql (fake visits, works before A's pipeline lands)"
	@echo "make reset    - delete the db and rebuild it seeded"
	@echo "make check    - run all five smoke checks. MUST pass before every push."
	@echo "make spend    - model-call token totals (check before the 2 AM backfill)"

db:
	@$(PY) -c "from palate import db; db.migrate(); print('schema applied')"

seed: db
	@$(PY) -c "from palate import db; n = db.seed(); print(f'seeded — {n} visits')"

reset:
	@rm -f palate.db palate.db-wal palate.db-shm
	@$(MAKE) --no-print-directory seed

# ---- smoke checks (TRD section 8). One owner per check. ----

check-db:
	@$(PY) -c "from palate import db; db.migrate(); n=db.seed(); assert n>0, 'seed loaded no visits'; print(f'check-db OK ({n} visits)')"

check-ingest:
	@$(PY) -m palate ingest.check

check-profile:
	@$(PY) -m palate profile.check

check-plan:
	@$(PY) -m palate plan.check

check-chat:
	@$(PY) -m palate chat.check

check: check-db check-ingest check-profile check-plan check-chat
	@echo "--- all checks passed ---"

spend:
	@$(PY) -m palate llm.spend
