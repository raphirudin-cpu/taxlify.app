web: FLASK_APP=run.py flask db upgrade && gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
worker: celery -A app.celery worker --beat --loglevel=info
