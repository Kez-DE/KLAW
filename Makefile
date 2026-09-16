.PHONY: run test test-all lint format typecheck check check-fix clean

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Cùng lane với CI (.github/workflows/ci.yml): `integration` cần Postgres đang
# chạy, `pending_review` chờ chủ dự án duyệt tay. `make test-all` khi muốn đủ.
test:
	pytest tests/ -v --tb=short -m "not integration and not pending_review"

test-all:
	pytest tests/ -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

# `check` KHÔNG ghi tệp: nó chạy trên cây làm việc đang sửa dở và trên diff đang
# được xem xét. `ruff format` sửa tệp, nên nó nằm ở `check-fix`, gọi tay.
check: lint test

check-fix: lint format test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
