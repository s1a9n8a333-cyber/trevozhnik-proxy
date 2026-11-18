FROM python:3.12-slim
WORKDIR /app
COPY travel_time.py .
ENV PORT=8080
EXPOSE 8080
CMD ["python3", "travel_time.py"]
