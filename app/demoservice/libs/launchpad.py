from demoservice.tasks.launchpad import (
    queue_start_launchpad_demo,
    queue_stop_launchpad_demo,
)

DEMO_PR_URL_TEMPLATE = '{repo_name}-{org_name}-pr-{pr}.run.demo.haus'


def get_demo_url(repo, pr):
    return "{repo}-launchpad-pr-{pr}.run.demo.haus".format(
        repo=repo,
        pr=pr
    )


def get_context_from_payload(payload):
    pr = payload["merge_proposal"].split("/")[-1]
    user = payload["new"]["source_git_repository"].split("/")[1]
    repo = payload["new"]["target_git_repository"].split("/")[2]
    branch = payload["new"]["source_git_path"].split("/")[-1]

    return dict(
        demo_url=get_demo_url(repo, pr),
        user=user,
        repo=repo,
        branch=branch,
        pr=pr
    )


def handle_webhook(event, payload):
    if event == "merge-proposal:0.1":
        handle_merge_proposal(payload)


def handle_merge_proposal(payload):
    action = payload["action"]
    context = get_context_from_payload(payload)

    if action == "created" or action == "modified":
        queue_start_launchpad_demo(context=context, **context)

    if action == "closed":
        queue_stop_launchpad_demo(context=context, **context)
