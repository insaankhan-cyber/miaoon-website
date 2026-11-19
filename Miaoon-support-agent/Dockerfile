FROM python:3.12-slim
WORKDIR /app
COPY . .
ENV PORT=8000
VOLUME /app/data
EXPOSE 8000
CMD ["python", "server.py"]
