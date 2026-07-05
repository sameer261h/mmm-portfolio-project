FROM python:3.11-slim

WORKDIR /app

COPY requirements-cloudrun.txt .
RUN pip install --no-cache-dir -r requirements-cloudrun.txt

COPY ads_agent/ ads_agent/
COPY streamlit_app.py .

# Cloud Run injects PORT; Streamlit must bind to 0.0.0.0 to be reachable.
ENV PORT=8080
EXPOSE 8080

CMD streamlit run streamlit_app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true
