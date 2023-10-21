.PHONY: dev
dev:
		@uvicorn main:app --reload

.PHONY: css
css:
		@npx tailwindcss -i ./assets/tailwind.css -o ./static/tailwind.css --watch
