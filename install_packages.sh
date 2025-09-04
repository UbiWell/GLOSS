#!/bin/bash
echo "Attempting to install packages from environment.yml..."

# Loop through each package in the environment.yml file
while IFS= read -r package; do
    echo "Installing $package with conda..."
    conda install -n base -y "$package" || \
    (echo "Conda failed for $package, trying pip..." && \
     pip install "$package" || \
     echo "Both conda and pip failed for $package, skipping.")
done < <(grep -oP '(?<=- )\S+' environment.yml)

conda clean -afy

