web: python manage.py migrate && gunicorn fetchbot.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4
