FROM python:3.11-slim
WORKDIR /app
COPY requirements-dashboard.txt /app/requirements-dashboard.txt
RUN python -m pip install --no-cache-dir -r requirements-dashboard.txt && python -m pip check
RUN useradd --create-home --uid 10001 dashboard
COPY dashboard /app/dashboard
ENV PYTHONPATH=/app
WORKDIR /app/dashboard
USER dashboard
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
