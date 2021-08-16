# rm -r .venv
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install wheel
pip install -r requirements_prod.txt
pip freeze > requirements.txt
pip install -r requirements_dev.txt