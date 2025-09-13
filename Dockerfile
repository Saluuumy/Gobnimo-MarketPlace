FROM python:3.11

ENV PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=Ecommerce.settings \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "Ecommerce.wsgi:application"]