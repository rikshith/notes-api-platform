# using a python base image
FROM python:3.11-slim
RUN useradd --create-home --uid 10001 appuser

# Set environment variables to optmize python bheviour inside the container
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory inside the container
WORKDIR /app

#copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

#copy the entire project into the container and set the user to a non-root user for security
COPY . /app/
USER appuser

# Expose the port that the application will run on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]




