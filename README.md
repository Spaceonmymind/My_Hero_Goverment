## Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

uvicorn app.main:app --reload
