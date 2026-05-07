FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --root-user-action=ignore -r requirements.txt
COPY proto /app/proto
COPY controller /app/controller
ENV PYTHONPATH=/app/proto/src
CMD ["python", "controller/controller.py"]