"""API credentials template.

Copy this file to `credentials.py` in the same directory and fill in your own
keys before running `gen_paraphrases.py` or `run_experiment.py`:

    cp credentials.example.py credentials.py

Each provider exposes an OpenAI-compatible endpoint. Model availability and
rate limits are provider-specific; see the paper's Section 4 (Experimental
setup) for the exact configuration used in the reported experiments.
"""

APINEX = {
    "base_url": "https://api.apinex.bond/v1",
    "api_key": "sk-YOUR-KEY-HERE",
}

AGNES = {
    "base_url": "https://apihub.agnes-ai.com/v1",
    "api_key": "sk-YOUR-KEY-HERE",
    "models": [
        "agnes-2.5-flash", "agnes-2.5-pro-alpha", "agnes-2.5-pro-beta",
        "agnes-3.0-flash", "agnes-3.0-pro",
    ],
}

ALIYUN = {
    # Any OpenAI-compatible endpoint works; the reported experiments used an
    # Aliyun Bailian (Model Studio) workspace endpoint.
    "base_url": "https://YOUR-ENDPOINT/compatible-mode/v1",
    "api_key": "sk-YOUR-KEY-HERE",
    "models": [
        "qwen3.8-max", "qwen3.8-omni-flash", "qwen3.7-flash",
    ],
}
