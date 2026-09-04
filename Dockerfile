# Use the official miniconda3 image as the base
FROM continuumio/miniconda3

# Set the working directory
WORKDIR /app

# Copy the environment file and install script to the Docker image
COPY environment_linux.yml .
RUN conda env create -f environment_linux.yml
# # Ensure the install script has execute permissions
# RUN chmod +x install_packages.sh

# # Run the install script using bash
# RUN /bin/bash ./install_packages.sh

# Activate the environment
SHELL ["conda", "run", "-n", "gloss-sensemaking", "/bin/bash", "-c"]

ENV PATH /opt/conda/envs/gloss-sensemaking/bin:$PATH
ENV CONDA_DEFAULT_ENV gloss-sensemaking

# Model config has to be baked into the image: autogen 0.4.0.dev2's
# DockerCommandLineCodeExecutor takes no env argument, so nothing can be
# injected at run time. Generated code imports data_streams/*_data.py, which
# import the summarizer agents, which build an LLM client at import time.
#
# Pass values at build time so no key is committed to this file:
#   docker build --build-arg GATEWAY_API_KEY="$GATEWAY_API_KEY" \
#     --platform linux/amd64 -f Dockerfile -t gloss-sensemaking-code .
#
# Note that anything baked in this way is readable via `docker history` and
# `docker inspect`, so treat the resulting image as holding the credential.
#
# These layers sit after the conda install on purpose: changing a key or model
# then rebuilds in seconds instead of re-solving the whole environment.
ARG GATEWAY_API_KEY=""
ARG USE_LOCAL_MODEL="True"
ARG LOCAL_MODEL_NAME="gemma4:31b"
ARG LOCAL_MODEL_BASE_URL="https://compute-gateway.europa.khoury.northeastern.edu"
ARG OPENAI_API_KEY=""
ARG AZURE_OPENAI_API_KEY=""
ARG AZURE_OPENAI_API_ENDPOINT=""
ARG MONGO_URI=""

# Local model (used when USE_LOCAL_MODEL is True)
ENV GATEWAY_API_KEY=$GATEWAY_API_KEY
ENV USE_LOCAL_MODEL=$USE_LOCAL_MODEL
ENV LOCAL_MODEL_NAME=$LOCAL_MODEL_NAME
ENV LOCAL_MODEL_BASE_URL=$LOCAL_MODEL_BASE_URL

# OpenAI / Azure (used when USE_LOCAL_MODEL is False)
ENV OPENAI_API_KEY=$OPENAI_API_KEY
ENV AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY
ENV AZURE_OPENAI_API_ENDPOINT=$AZURE_OPENAI_API_ENDPOINT

ENV MONGO_URI=$MONGO_URI
ENV RUNNING_IN_DOCKER=true

# Set the command to run when starting the container
CMD ["python"]
