.PHONY: test check render clean

test:
	python -m pytest tests/ -v

check:
	python scripts/render_course.py --check $(COURSE)

render:
	python scripts/render_course.py $(COURSE)

clean:
	rm -rf content/*/index.html content/*/assets/ content/*/__pycache__/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
