import os

USE_AZURE = False
USE_GPT5 = False
ONLY_CODE_FUNCTIONS = True
VERBOSE = True
DOCKER_NAME = "gloss-sensemaking-code"
USE_CSV = True

# Master switch for the model backend.
#   True  -> every LLM call goes to a local Ollama model (Khoury GPU gateway).
#            No OpenAI/Azure key is needed; set GATEWAY_API_KEY instead.
#   False -> use OpenAI / Azure as before (honours USE_AZURE and USE_GPT5).
USE_LOCAL_MODEL = os.getenv("USE_LOCAL_MODEL", "True").lower() == "true"

# Settings below are read only when USE_LOCAL_MODEL is True.

# Model tag as it appears in /api/tags on the cluster. The gateway keeps an
# allowlist of servable models and returns 403 with an "allowed_models" list
# for anything else, so this must be a model the cluster actually permits.
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "gemma4:31b")

# Gateway base URL. Requires the Northeastern VPN from off-campus. A worker can
# also be addressed directly (e.g. http://129.10.112.25:11434) from on-campus,
# which skips the gateway's auth and allowlist.
LOCAL_MODEL_BASE_URL = os.getenv(
    "LOCAL_MODEL_BASE_URL", "https://compute-gateway.europa.khoury.northeastern.edu"
)

# Environment variable holding the gateway bearer token. Requests go out without
# an Authorization header if it is unset, which is what a direct worker wants.
LOCAL_MODEL_API_KEY_ENV = os.getenv("LOCAL_MODEL_API_KEY_ENV", "GATEWAY_API_KEY")

LOCAL_MODEL_TEMPERATURE = float(os.getenv("LOCAL_MODEL_TEMPERATURE", "0"))

# Cap on generated tokens; -1 means no cap. Keep this generous (or -1) for
# thinking models, whose reasoning tokens count against the budget before any
# answer text is produced.
LOCAL_MODEL_NUM_PREDICT = int(os.getenv("LOCAL_MODEL_NUM_PREDICT", "-1"))

# Thinking models (gemma4, gpt-oss) emit reasoning into message.thinking before
# filling message.content. GLOSS parses most replies with JsonOutputParser and
# does not use the reasoning, so thinking is off by default: it is faster and
# removes the risk of the token budget being spent before any JSON is emitted.
LOCAL_MODEL_THINK = os.getenv("LOCAL_MODEL_THINK", "False").lower() == "true"

# Seconds. Large models can take minutes before the first token arrives.
LOCAL_MODEL_TIMEOUT = int(os.getenv("LOCAL_MODEL_TIMEOUT", "600"))
