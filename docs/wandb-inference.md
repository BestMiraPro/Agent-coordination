# W&B Inference setup

The worker supports W&B Serverless Inference through the OpenAI-compatible
endpoint:

```text
https://api.inference.wandb.ai/v1
```

A W&B key can be supplied as either `WANDB_API_KEY` or the vendor-neutral
`INFERENCE_API_KEY`. Secrets are read only from runtime environment settings;
they are never persisted in model profiles, model calls, run events, or Git.

When `INFERENCE_PROVIDER=wandb` and `INFERENCE_DISCOVER_MODELS=true`, worker
startup calls W&B's documented `GET /models` endpoint using bearer
authentication. Startup therefore validates the credential and discovers every
model currently available to the account, up to `INFERENCE_MODEL_LIMIT`.

`INFERENCE_MODEL` remains the primary model prior. Newly discovered models are
registered with neutral quality priors so they become available to the adaptive
router without being assumed superior before benchmark evidence exists.

Some W&B models may expose chat completions without strict JSON-schema response
format. When such a model rejects `response_format`, the provider retries once
without that optional parameter. Research prompts still require JSON and the
normal structured-output parser remains the acceptance gate.

No API credential belongs in this repository. Use a local `.env`, deployment
secret store, or GitHub Actions secret.
