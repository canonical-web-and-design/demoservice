import logging
from demoservice.libs.demos import (
    start_launchpad_demo,
    stop_launchpad_demo
)
from demoservice.tasks import app


@app.task(bind=True, max_retries=2)
def start_launchpad_demo_task(
    self,
    demo_url,
    user,
    repo,
    branch,
    pr,
    context,
    **kwargs
):
    logger = logging.getLogger(__name__)
    logger.info("Starting start_launchpad_demo_task task for %s", demo_url)
    try:
        return start_launchpad_demo(
            demo_url=demo_url,
            user=user,
            repo=repo,
            branch=branch,
            pr=pr,
            context=context
        )
    except Exception as e:
        logger.error(e)
        # Retry on failure with a growing cooldown
        retry_count = self.request.retries
        seconds_to_wait = 2 * retry_count
        raise self.retry(exc=e, countdown=seconds_to_wait)


@app.task(bind=True, max_retries=2)
def stop_launchpad_demo_task(
    self,
    demo_url,
    context,
    **kwargs
):
    logger = logging.getLogger(__name__)
    logger.info("Starting stop_launchpad_demo_task task for %s", demo_url)

    try:
        return stop_launchpad_demo(
            demo_url=demo_url,
            context=context
        )
    except Exception as e:
        logger.error(e)
        # Retry on failure with a growing cooldown
        retry_count = self.request.retries
        seconds_to_wait = 2 * retry_count
        raise self.retry(exc=e, countdown=seconds_to_wait)


def queue_start_launchpad_demo(
    demo_url,
    user,
    repo,
    branch,
    pr,
    context
):
    logger = logging.getLogger(__name__)
    logger.info(
        "Adding demo to queue for %s/%s on PR %s (%s)",
        "launchpad",
        repo,
        pr,
        demo_url,
    )

    start_launchpad_demo_task.delay(
        context=context,
        **context
    )


def queue_stop_launchpad_demo(
    demo_url,
    user,
    repo,
    branch,
    pr,
    context
):
    logger = logging.getLogger(__name__)
    logger.info(
        "Adding demo removal to queue for %s/%s on PR %s (%s)",
        "launchpad",
        repo,
        pr,
        demo_url,
    )

    stop_launchpad_demo_task.delay(
        context=context,
        **context
    )
