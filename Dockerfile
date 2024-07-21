# Use an official Python runtime as a parent image

FROM python:3.10-slim



# Set the working directory in the container

WORKDIR /app



# Copy the requirements file into the container

COPY requirements.txt .



# Install any needed packages specified in requirements.txt

RUN pip install --no-cache-dir -r requirements.txt



# Copy the rest of the working directory contents into the container

COPY . ./app



# Make port 80 available to the world outside this container

EXPOSE 80



# Define environment variable

ENV NAME autoforwardbot



# Run the bot when the container launches

CMD ["python", "main.py"]
