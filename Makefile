.PHONY: dev
dev:
		@uvicorn server:app --reload
