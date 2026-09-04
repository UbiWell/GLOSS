# GLOSS Setup Guide

This guide walks you through setting up GLOSS (Group of LLMs for Open-Ended Sensemaking) on your local machine. To read more about GLOSS, please refer to the 📚 [full paper for GLOSS](https://dl.acm.org/doi/10.1145/3749474).

## Prerequisites Setup

### 1. Install Required Software

- **Anaconda**: Download from [anaconda.com](https://anaconda.com) if not already installed
- **Docker**: Download from [docker.com](https://docker.com) if not already installed  
- **Git**: Most computers have this, but download from [git-scm.com](https://git-scm.com) if needed

## Getting the Code

### 2. Download the Repositories

Open your terminal/command prompt and navigate to your working directory 

```bash
# Clone the public github GLOSS repository
git clone https://github.com/UbiWell/GLOSS.git
# or using SSH:
# git clone git@github.com:UbiWell/GLOSS.git
```
If you want to add stress detection model:
Clone the stress detection algorithm inside the GLOSS repo. GLOSS uses stress detection models by  📚[Varun et al](https://pmc.ncbi.nlm.nih.gov/articles/PMC9523764/) to detect stress using IBI data

```bash
cd GLOSS

git clone https://github.com/UbiWell/stress-detection-algorithm-code-python.git
# or using SSH:
# git clone git@github.com:UbiWell/stress-detection-algorithm-code-python.git
```
Your folder structure should now look like:
Working dir/GLOSS/stress-detection-algorithm-code-python
Install the package:
```bash
cd stress-detection-algorithm-code-python
pip install -e .
```

***What this does:*** Downloads two code repositories needed for GLOSS to work properly.

## Setting Up Python Environment

### 3. Create the Conda Environment

```bash
# Go into the GLOSS repository if it's not your current directory
cd GLOSS

# Create a new Python environment (The default name is gloss-sensemaking). Use the respective .yml file for Mac or Linux installations
conda env create -f environment_mac.yml (OPTIONAL: -n preferred-env-name)
or
conda env create -f environment_linux.yml (OPTIONAL: -n preferred-env-name)

# Activate your new environment
conda activate gloss-sensemaking (or preferred-env-name)
```
***What this does:*** Creates an isolated Python environment with all the right packages so GLOSS works correctly.

### 4. Setting up Config and ENV variables
Go to `agents/config.py` and set up config variables. By default, GLOSS uses GPT-4o:

```bash
USE_LOCAL_MODEL = True #(True to run entirely on a local Ollama model, no OpenAI key needed)
USE_AZURE = False #(True if using Azure deployment)
USE_GPT5 = False #(True if using GPT-5)
ONLY_CODE_FUNCTIONS = True #(True if all runs use code generation)
VERBOSE = True #(True if need more verbosity when running sensemaking_process.py)
USE_CSV = True #(True if using CSV as data, keep it true as demo uses csv data)
DOCKER_NAME = "gloss-sensemaking-code" # (name of Docker to run LLM-generated code)
```

`USE_LOCAL_MODEL` takes priority over `USE_AZURE` and `USE_GPT5`. Set it to
`False` to fall back to the OpenAI/Azure behaviour described below.

#### Set ENV variables:
OPENAI_API_KEY or AZURE_OPENAI_API_ENDPOINT and AZURE_OPENAI_API_KEY based on whether you are calling OpenAI APIs directly or through Azure deployment.

***Example***
```bash
export AZURE_OPENAI_API_KEY="your_api_key_here"
Save and reload your shell:

source ~/.bashrc   # or ~/.zshrc
```

### 4b. Running entirely on a local model (no OpenAI key)

With `USE_LOCAL_MODEL = True`, every agent — including the code-generating
coding agent — talks to an Ollama model on the Khoury GPU cluster instead of
OpenAI. The only credential needed is the cluster gateway key:

```bash
export GATEWAY_API_KEY="your_gateway_key_here"
```

You must be on the Northeastern VPN (or on campus) to reach the gateway.
Everything else is tunable in `agents/config.py`, and each setting can also be
overridden by an environment variable of the same name:

| Setting | Default | Notes |
|---|---|---|
| `LOCAL_MODEL_NAME` | `gemma4:31b` | Must be a model the gateway permits — see below |
| `LOCAL_MODEL_BASE_URL` | `https://compute-gateway.europa.khoury.northeastern.edu` | A worker (e.g. `http://129.10.112.25:11434`) works from on-campus and needs no key |
| `LOCAL_MODEL_THINK` | `False` | Thinking models emit reasoning before their answer; off is faster and keeps JSON replies clean |
| `LOCAL_MODEL_NUM_PREDICT` | `-1` (uncapped) | Keep generous: reasoning tokens count against this budget |
| `LOCAL_MODEL_TEMPERATURE` | `0` | |
| `LOCAL_MODEL_TIMEOUT` | `600` | Seconds; large models are slow to first token |

Check which models the cluster will actually serve before running GLOSS — the
gateway keeps an allowlist and returns 403 for anything else:

```bash
curl -H "Authorization: Bearer $GATEWAY_API_KEY" \
  https://compute-gateway.europa.khoury.northeastern.edu/api/tags
```

Verify the setup end to end with:

```bash
python -m agents.local_model
```

***Known limitation:*** the RAG agent (`agents/rag_based_agent.py`) needs an
embedding model, and the cluster's Ollama workers run without `--embeddings`.
That agent still requires `OPENAI_API_KEY`; it sits outside the main
sensemaking flow, which runs fully local.

## Docker Setup

### 5. Add Your API Keys

Credentials are passed as **build args** rather than edited into the Dockerfile,
so nothing secret gets committed. They have to be baked into the image because
autogen 0.4.0.dev2's `DockerCommandLineCodeExecutor` cannot inject environment
variables at run time, and the generated code imports the summarizer agents,
which construct an LLM client on import.

Treat the built image as holding the credential — `docker history` and
`docker inspect` will show it.

### 6. Build the Docker Container

Keep using `environment_linux.yml`: the image is Linux whatever your host is.
On Apple Silicon, add `--platform linux/amd64`, because that file pins
linux-64 package builds that will not solve on arm64.

```bash
# From the GLOSS dir, build the Docker image  (this may take a few minutes)
docker build --platform linux/amd64 \
  --build-arg GATEWAY_API_KEY="$GATEWAY_API_KEY" \
  -f Dockerfile -t gloss-sensemaking-code . # (use the name set up in config)
```

Swap `--build-arg GATEWAY_API_KEY=...` for `--build-arg OPENAI_API_KEY=...`
when running against OpenAI instead. `LOCAL_MODEL_NAME` and
`LOCAL_MODEL_BASE_URL` are build args too, defaulting to the same values as
`agents/config.py`.
***What this does:*** Creates a containerized environment that packages everything GLOSS needs to run consistently.

## Running GLOSS
### 7. Sample Data
The first author provided one day (08/28/2025) of their data as sample data, except the location database in CSV Format. 
So after setting up GLOSS, users can query the data.

### 8. Customize and Run
`work_dir` for the code-executor container is now resolved from the repo
location automatically; set `GLOSS_REPO_ROOT` only if the repo lives elsewhere.

```bash
# Edit the main script to set your research question
vi sensemaking_process.py  # or use your preferred editor
```
```python
# Change presentation instructions and query to run:
# Example shown below
presentation_instructions_ = '''
clear and concise
'''
query = '''
on aug 28 2025, for test004 what was most used app by duration?'''
SenseMaker(
   query,
   presentation_instructions_).make_sense(verbose=VERBOSE)
```

```bash
# Run GLOSS!
python sensemaking_process.py
```
***What this does:*** Starts the sensemaking process with your custom query.

GLOSS runs the sensemaking process and you can see every step of the process and the final answer.

### 9. You can also use GLOSS UI for running queries
 ```bash streamlit run sensemaking.ui ```

 [![Figure 1](images/sensemaking_ui.jpg) Figure 1: Sensemaking Process ](images/sensemaking_ui.jpg)

## Adding your own database
#### 1. Copy the template:
   ```bash
   cp data_streams/database_template.py data_streams/my_new_database.py
   ```
#### 2. Uncomment the code as code in my_new_database.py is commented. Fill in the metadata:
   ```python
   database_info = {
       "name": "my_new_database", 
       "info": "Description of your database",
       "device": "Phone",  # or "Watch", "Sensor", etc.
       "additional_instructions": "Any special instructions"
   }
   ```

#### 3. Add function metadata for LLMs:
   ```python
   functions = {
       "FUNC1": {
           "name": "get_my_data",
           "description": "Retrieves data from your database",
           "usecase": ["code_generation", "function_calling"],
           "params": {
               "user_id": {"type": "str", "description": "User identifier"},
               "start_time": {"type": "str", "description": "Start time"},
               "end_time": {"type": "str", "description": "End time"}
           },
           "returns": "A list of data records",
           "example": "[{'timestamp': '2024-01-01 12:00:00', 'value': 42.5}]"
       }
   }
   ```

#### 4. Add your actual function implementations:
   ```python
   def get_my_data(user_id: str, start_time: str, end_time: str):
       # Your implementation here
       pass
   
   function_refs = {
       "get_my_data": get_my_data
       # Add more functions
   }
   ```

#### 5. That's it! The registry will automatically discover and load your new database.

   ```python
   database_info = {
       "name": "my_new_database", 
       "info": "Description of your database",
       "device": "Phone",  # or "Watch", "Sensor", etc.
       "additional_instructions": "Any special instructions"
   }
   ```

#### If you use this code please cite:
***Akshat Choube, Ha Le, Jiachen Li, Kaixin Ji, Vedant Das Swain, and Varun Mishra. 2025. GLOSS: Group of LLMs for Open-ended Sensemaking of Passive Sensing Data for Health and Wellbeing. Proc. ACM Interact. Mob. Wearable Ubiquitous Technol. 9, 3, Article 76 (September 2025), 32 pages. https://doi.org/10.1145/3749474***


**Feel free to open issues in the repository or contact choube.a@northeastern.edu if you need additional help setting up GLOSS locally.**
