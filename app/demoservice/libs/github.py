import re
from demoservice.tasks import queue_start_demo, queue_stop_demo


GITHUB_PR_URL_REGEX = re.compile(
    "^https:\/\/github.com\/(?P<user>[-._\w]+)\/(?P<repo>[-._\w]+)\/pull\/(?P<pr>\d+)$",
    re.IGNORECASE,
)


def is_valid_github_url(url):
    return GITHUB_PR_URL_REGEX.fullmatch(url) is not None


def get_github_info_from_url(url):
    match = GITHUB_PR_URL_REGEX.fullmatch(url)

    if not match:
        return None

    return dict(
        pr=match.group("pr"),
        repo=match.group("repo"),
        user=match.group("user"),
    )


def handle_webhook(event, payload):
    if event == "pull_request":
        handle_pull_Request(payload)


def handle_pull_Request(payload):
    action = payload["action"]
    pull_request_id = payload["number"]
    repo_owner = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]
    sender = payload["sender"]["login"]

    if action == "opened" or action == "synchronize":
        queue_start_demo(
            github_user=repo_owner,
            github_repo=repo_name,
            github_pr=pull_request_id,
            github_sender=sender,
            github_verify_sender=True,
            send_github_notification=(action == "opened"),
        )

    if action == "closed":
        queue_stop_demo(
            github_user=repo_owner,
            github_repo=repo_name,
            github_pr=pull_request_id,
        )
