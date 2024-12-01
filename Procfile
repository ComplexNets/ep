# Run migrations before starting the web server
web: python manage.py migrate && gunicorn ep.wsgi --log-file -
