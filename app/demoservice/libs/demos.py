import fileinput
import json
import logging
import os
import re
import requests
import shutil
import socket
import yaml
from django.conf import settings
from github3 import login
from subprocess import Popen

from demoservice.logging import get_demo_logger


DEMO_PR_URL_TEMPLATE = '{repo_name}-pr-{github_pr}.run.demo.haus'
GITHUB_CLONE_URL = 'https://github.com/{github_user}/{github_repo}.git'


def _get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


def _is_repo_collaborator(repo_owner, repo_name, user):
    gh = login('-', password=settings.GITHUB_TOKEN)
    repo = gh.repository(repo_owner, repo_name)
    return repo.is_collaborator(user)


def get_demo_context(
    demo_url,
    github_user,
    github_repo,
    github_pr=None,
):
    return {
        'demo_url': demo_url,
        'github_user': github_user,
        'github_repo': github_repo,
        'github_pr': github_pr,
    }


def get_demo_url_pr(repo_name, github_pr):
    return DEMO_PR_URL_TEMPLATE.format(
        repo_name=repo_name,
        github_pr=github_pr,
    )


def notify_github_pr(
    message,
    github_user,
    github_repo,
    github_pr,
    context=None,
):
    if context:
        logger = get_demo_logger(__name__, **context)
    else:
        logger = logging.getLogger(__name__)

    comment = {
        'body': message,
    }

    api_url = (
        'https://api.github.com'
        '/repos/{github_user}/{github_repo}/'
        'issues/{github_pr}/comments'
    ).format(
        github_user=github_user,
        github_repo=github_repo,
        github_pr=github_pr,
    )

    logger.debug('GitHub comment API URL: %s', api_url)
    logger.info('Commenting on pull request: %s', comment['body'])

    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logger.warning('Missing GITHUB_TOKEN environment variable')
        return None

    api_headers = {
        'Authorization': 'token {token}'.format(token=github_token)
    }

    if settings.DEBUG:
        logger.debug('Simulating GitHub notification while DEBUG is active')
        return True

    session = requests.session()
    request = session.post(api_url, json.dumps(comment), headers=api_headers)
    if request.status_code == 201:
        logger.info('Successfully notified Pull Request')
    else:
        logger.warning('Could not notify Pull Request: %s', request.content)
        raise Exception(
            'Failed to notify Github: {content}'.format(
                content=request.content
            )
        )


def start_demo(
    demo_url,
    github_user,
    github_repo,
    github_pr,
    github_sender=None,
    github_verify_sender=True,
    context=None,
):
    if context:
        logger = get_demo_logger(__name__, **context)
    else:
        logger = logging.getLogger(__name__)

    if github_verify_sender:
        logger.debug('Verifying if user is collaborator of repo',)
        if not github_sender:
            logger.error('GitHub webhook sender is not set for verification')
            return None
        logger.debug(
            'Verifying %s is a collaborator of %s/%s',
            github_sender,
            github_user,
            github_repo,
        )
        if not _is_repo_collaborator(github_user, github_repo, github_sender):
            logger.info(
                "%s is not a collaborator of this repo", github_sender
            )
            return (
                "User is not a collaborator of this repo. "
                "Please start demo manually."
            )
        logger.info('User is a collaborator of the repo')

    logger.info('Preparing demo: %s', demo_url)

    os.makedirs(settings.DEMO_DIR, exist_ok=True)
    local_path = os.path.join(settings.DEMO_DIR, demo_url)
    run_command_path = os.path.join(local_path, 'run')

    # Clone repo and update PR
    if not os.path.isdir(local_path):
        clone_url = GITHUB_CLONE_URL.format(
            github_user=github_user,
            github_repo=github_repo,
        )
        logger.info('Cloning git repo: %s', clone_url)
        p = Popen(['git', 'clone', clone_url, local_path])
        return_code = p.wait()
        if return_code > 0:
            logger.error('Error while cloning %s', clone_url)
            return False
    elif os.path.exists(run_command_path):
        logger.info('Cleaning previous run script')
        p = Popen(
            ['./run', 'clean'],
            cwd=local_path,
        )
        p.wait()

    p = Popen(['git', 'reset', '--hard', 'HEAD'], cwd=local_path)
    p.wait()
    if github_pr:
        logger.info('Pulling PR branch for %s', github_pr)
        p = Popen(
            ['git', 'pr', str(github_pr)],
            cwd=local_path,
        )
        return_code = p.wait()
        if return_code > 0:
            logger.error('Error while pulling PR %s branch', github_pr)
            return False

    # Check for the run command to continue
    if not os.path.exists(run_command_path):
        message = 'No ./run found. Unable to start demo.'
        logger.info(message)
        return message

    # Check to see it is updated for this script
    docker_option_string = '${run_serve_docker_opts}'
    run_file_contents = open(run_command_path).read()
    if docker_option_string not in run_file_contents:
        message = './run is not compatible for demos and needs updating.'
        logger.info(message)
        return message

    # Stop bower complaining about running as root...
    # This actually updates the run command for now and resets on rerun
    bower_string = 'bower install'
    bower_string_for_root = 'bower install --allow-root'
    if bower_string_for_root not in run_file_contents:
        for line in fileinput.input(run_command_path, inplace=True):
            print(line.replace(bower_string, bower_string_for_root), end='')

    # Set the docker name if not created
    docker_project_path = os.path.join(local_path, '.docker-project')
    if not os.path.exists(docker_project_path):
        with open(docker_project_path, "w") as project_file:
            project_file.write(demo_url)

    demo_url_path = ''

    # Check for Jekyll base paths
    jekyll_config_name = r'^_config\.ya?ml$'
    jekyll_config_path = False
    for _file in os.listdir(local_path):
        # if fnmatch.fnmatch(_file, jekyll_config_name):
        if re.search(jekyll_config_name, _file):
            jekyll_config_path = os.path.join(local_path, _file)
            break

    if jekyll_config_path:
        logger.info('Found Jekyll config, looking for baseurl')
        with open(jekyll_config_path, 'r') as stream:
            try:
                jekyll_config = yaml.load(stream)
            except yaml.YAMLError as e:
                logger.error('Error parsing Jekyll config YAML: %s', e)
        demo_url_path = jekyll_config.get('baseurl', '').strip('/')
        logger.info('Setting demo path to %s', demo_url_path)

    # Start ./run server with extra options
    demo_url_full = ''.join(['http://', demo_url, '/'])
    if demo_url_path:
        demo_url_full = ''.join([demo_url_full, demo_url_path, '/'])
    logger.info('Starting demo: %s', demo_url_full)

    port = _get_open_port()

    docker_options = ''
    docker_labels = {
        'rap.host': demo_url,
        'traefik.enable': 'true',
        'traefik.frontend.rule': 'Host:{url}'.format(url=demo_url),
        'traefik.port': port,
        'run.demo': True,
        'run.demo.url': demo_url,
        'run.demo.url_full': demo_url_full,
        'run.demo.github_user': github_user,
        'run.demo.github_repo': github_repo,
        'run.demo.github_pr': github_pr,
    }
    for key, value in docker_labels.items():
        docker_options += " -l {key}={value}".format(key=key, value=value)
    logger.debug('Docker options: %s', docker_options)

    # We are going to inject all env var items beginning with DEMO_OPT_
    # This allows us to quickly set up global options and secrets for apps.
    docker_env_opts = {
        k: v for k, v in os.environ.items() if k.startswith('DEMO_OPT_')
    }
    for key, value in docker_env_opts.items():
        docker_options += " -e {key}={value}".format(key=key[9:], value=value)

    run_env = os.environ.copy()
    run_env["CANONICAL_WEBTEAM_RUN_SERVE_DOCKER_OPTS"] = docker_options
    serve_args = ''
    if 'tutorials' in github_repo:
        serve_args = './tutorials/*/'
    p = Popen(
        ['./run', 'serve', '--detach', '--port', str(port), serve_args],
        cwd=local_path,
        env=run_env,
    )
    return_code = p.wait()
    if return_code > 0:
        raise Exception('Error starting ./run')

    message = 'Starting demo at: {demo_url}'.format(demo_url=demo_url_full)
    return message


def stop_demo(
    demo_url,
    context=None,
):
    if context:
        logger = get_demo_logger(__name__, **context)
    else:
        logger = logging.getLogger(__name__)
    logger.info('Stopping demo: %s', demo_url)

    local_path = os.path.join(settings.DEMO_DIR, demo_url)
    if not os.path.isdir(local_path):
        return

    # Check for the run command to clean
    run_command_path = os.path.join(local_path, 'run')
    if os.path.exists(run_command_path):
        logger.info('Running clean command')
        p = Popen(
            ['./run', 'clean'],
            cwd=local_path,
        )
        p.wait()

    logger.info('Deleting files for %s', demo_url)
    shutil.rmtree(local_path)
