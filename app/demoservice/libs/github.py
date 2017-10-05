from demoservice.tasks import (
    queue_start_demo,
    queue_stop_demo,
)


def handle_webhook(event, payload):
    if event == 'pull_request':
        handle_pull_Request(payload)


def handle_pull_Request(payload):
    action = payload['action']
    pull_request_id = payload['number']
    repo_owner = payload['repository']['owner']['login']
    repo_name = payload['repository']['name']
    sender = payload['sender']['login']

    if action == 'opened' or action == 'synchronize':
        queue_start_demo(
            github_user=repo_owner,
            github_repo=repo_name,
            github_pr=pull_request_id,
            github_sender=sender,
            github_verify_sender=True,
            send_github_notification=(action == 'opened'),
        )

    if action == 'closed':
        queue_stop_demo(
            github_user=repo_owner,
            github_repo=repo_name,
            github_pr=pull_request_id,
        )
