import logging


def get_demo_logger(
    logger_name,
    demo_url,
    github_user,
    github_repo,
    github_pr=None,
):
    extra = {
        'run.demo.url': demo_url,
        'run.demo.github_user': github_user,
        'run.demo.github_repo': github_repo,
        'run.demo.github_pr': github_pr,
    }
    logger = logging.getLogger(logger_name)
    return logging.LoggerAdapter(logger, extra)
