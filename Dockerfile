# Dockerfile
# Use a slim Python image as a base
FROM python:3.11-slim

# Set environment variables to run the application in an unbuffered mode
ENV PYTHONUNBUFFERED 1
ENV APP_HOME /app

# Create the application directory and set it as the working directory
RUN mkdir $APP_HOME
WORKDIR $APP_HOME

# Copy the requirements file and install dependencies
# We assume the user has a requirements.txt file with all necessary packages
# Streamlit, pandas, requests, google-genai, fpdf2, newsapi-python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all the application files (Python scripts and control file)
COPY run_agent_loop.py .
COPY dashboard.py .
COPY control_file.json .

# Create the memory file if it doesn't exist, to ensure the volume is set up
RUN touch memory_log.json

# Expose the Streamlit port (8501)
EXPOSE 8501

# The CMD is intentionally left blank here. We will use a dedicated
# start script and docker-compose to run the two services.