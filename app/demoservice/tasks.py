import os
from celery import Celery, chain

from demoservice.libs.demos import (
    get_demo_context,
    get_demo_url_pr,
    notify_github_pr,
    start_demo,
    stop_demo,
)
from demoservice.logging import get_demo_logger

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'demoservice.settings')

app = Celery('demoservice')

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True, max_retries=2)
def start_demo_task(
    self,
    demo_url,
    github_user,
    github_repo,
    github_pr,
    context,
    **kwargs
):
    logger = get_demo_logger(__name__, **context)
    logger.debug('Starting start_demo_task task for %s', demo_url)

    try:
        return start_demo(
            demo_url=demo_url,
            github_user=github_user,
            github_repo=github_repo,
            github_pr=github_pr,
            context=context,
        )
    except Exception as e:
        logger.error(e)
        # Retry on failure with a growing cooldown
        retry_count = self.request.retries
        seconds_to_wait = 2 * retry_count
        raise self.retry(exc=e, countdown=seconds_to_wait)


@app.task(bind=True, max_retries=2)
def stop_demo_task(
    self,
    demo_url,
    context,
    **kwargs
):
    logger = get_demo_logger(__name__, **context)
    logger.debug('Running the stop_demo task for %s', demo_url)

    try:
        return stop_demo(demo_url=demo_url, context=context)
    except Exception as e:
        logger.error(e)
        # Retry on failure with a growing cooldown
        retry_count = self.request.retries
        seconds_to_wait = 2 * retry_count
        raise self.retry(exc=e, countdown=seconds_to_wait)


@app.task(bind=True, max_retries=3)
def notify_github_task(
    self,
    message,
    demo_url,
    github_user,
    github_repo,
    github_pr,
    context,
    **kwargs
):
    logger = get_demo_logger(__name__, **context)
    logger.debug('Starting notify_github task for %s', demo_url)

    if not message:
        logger.debug('No notification message to send for %s', demo_url)
        return False

    try:
        return notify_github_pr(
            message=message,
            github_user=github_user,
            github_repo=github_repo,
            github_pr=github_pr,
            context=context,
        )
    except Exception as e:
        logger.error(e)
        # If the notification fails, retry with a growing cooldown
        retry_count = self.request.retries
        seconds_to_wait = 3 * retry_count + 1
        raise self.retry(exc=e, countdown=seconds_to_wait)


def queue_start_demo(
    github_user,
    github_repo,
    github_pr,
    send_github_notification=False,
):
    demo_url = get_demo_url_pr(github_repo, github_pr)
    context = get_demo_context(
        demo_url=demo_url,
        github_user=github_user,
        github_repo=github_repo,
        github_pr=github_pr,
    )
    logger = get_demo_logger(__name__, **context)
    logger.info(
        'Adding demo to queue for %s/%s on PR %s (%s)',
        github_user,
        github_repo,
        github_pr,
        demo_url,
    )

    tasks = [
        start_demo_task.s(context=context, **context)
    ]
    if send_github_notification:
        tasks.append(notify_github_task.s(context=context, **context))
    chain(*tasks).apply_async()


def queue_stop_demo(
    github_user,
    github_repo,
    github_pr,
):
    demo_url = get_demo_url_pr(github_repo, github_pr)
    context = get_demo_context(
        demo_url=demo_url,
        github_user=github_user,
        github_repo=github_repo,
        github_pr=github_pr,
    )
    logger = get_demo_logger(__name__, **context)
    logger.info(
        'Adding demo removal to queue for %s/%s on PR %s (%s)',
        github_user,
        github_repo,
        github_pr,
        demo_url,
    )

    stop_demo_task.delay(context=context, **context)
