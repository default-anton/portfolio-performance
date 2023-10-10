.PHONY: dev
dev:
		@uvicorn main:app --reload
