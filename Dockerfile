# Use the official miniconda3 image as the base
FROM continuumio/miniconda3

# Set the working directory
WORKDIR /app

ENV AZURE_OPENAI_API_KEY="add your key"
ENV AZURE_OPENAI_API_ENDPOINT="add your endpoint"
ENV MONGO_URI="add your mongo URI"
ENV OPENAI_API_KEY=""
ENV RUNNING_IN_DOCKER=true

# Copy the environment file and install script to the Docker image
COPY environment_linux.yml .
RUN chmod +x environment_linux.yml
RUN conda env create -f environment_linux.yml   
# # Ensure the install script has execute permissions
# RUN chmod +x install_packages.sh

# # Run the install script using bash
# RUN /bin/bash ./install_packages.sh

COPY stress-detection-algorithm-code-python /app/repo/stress-detection-algorithm-code-python

# Activate conda env in shell so pip/build run in same process with env's setuptools (avoids pkg_resources missing in isolated build)
RUN /bin/bash -c "source $(conda info --base)/etc/profile.d/conda.sh && conda activate gloss-sensemaking && pip install --no-build-isolation -e ./repo/stress-detection-algorithm-code-python/"

# Activate the environment
SHELL ["conda", "run", "-n", "gloss-sensemaking", "/bin/bash", "-c"]

ENV PATH /opt/conda/envs/gloss-sensemaking/bin:$PATH
ENV CONDA_DEFAULT_ENV gloss-sensemaking

# Set the command to run when starting the container
CMD ["python"]
