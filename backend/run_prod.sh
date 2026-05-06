# Optional: kill any zombie processes first
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Run the app
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload