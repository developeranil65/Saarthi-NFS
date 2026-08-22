FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better caching
COPY pyproject.toml .
RUN pip install .

# Copy the rest of the application
COPY . .

# Set PYTHONPATH so python can find the saarthi module inside src/
ENV PYTHONPATH=/app/src

# Hugging Face Spaces expose port 7860
EXPOSE 7860

# Run the FastAPI server
CMD ["uvicorn", "saarthi.main:app", "--host", "0.0.0.0", "--port", "7860"]
