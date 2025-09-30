import os, json, urllib.request

def send_slack(text: str, webhook_env="SLACK_WEBHOOK_URL"):
    url = os.getenv(webhook_env)
    if not url:
        print("WARN notify_slack: SLACK_WEBHOOK_URL not set; skipping.")
        return
    data = {"text": text}
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        if r.status >= 300:
            raise RuntimeError(f"Slack webhook failed: {r.status}")
