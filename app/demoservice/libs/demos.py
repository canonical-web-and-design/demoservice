import fileinput
import json
import logging
import os
import re
import urllib
import docker
import requests
import shutil
import socket
import yaml
from distutils.version import StrictVersion
from subprocess import Popen, check_output
from django.conf import settings
from github3 import login
from github3.models import GitHubError
from launchpadlib.launchpad import Launchpad
from demoservice.logging import get_demo_logger

MIN_RUNSCRIPT_VERSION = '2.0.0'
DEMO_PR_URL_TEMPLATE = '{repo_name}-{org_name}-pr-{github_pr}.run.demo.haus'
GITHUB_CLONE_URL = 'https://github.com/{github_user}/{github_repo}.git'


def _get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


def _is_github_repo_collaborator(repo_owner, repo_name, user):
    gh = login('-', password=settings.GITHUB_TOKEN)
    repo = gh.repository(repo_owner, repo_name)
    return repo.is_collaborator(user)


def _is_launchpad_team_member(team_name, person_name):
    lp = Launchpad.login_anonymously('demoservice', 'production')
    try:
        team = lp.people[team_name]
        members = team.getMembersByStatus(status="Approved")
        for member in members:
            # Check for a username starting with '~' too.
            if member.name == person_name or member.name == person_name[1:]:
                return True
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(e)

    return False


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


def get_demo_url_pr(org_name, repo_name, github_pr):
    return DEMO_PR_URL_TEMPLATE.format(
        org_name=org_name.replace(".", "-"),
        repo_name=repo_name.replace(".", "-"),
        github_pr=github_pr,
    ).lower()


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

    github_token = settings.GITHUB_TOKEN
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
        try:
            if not _is_github_repo_collaborator(
                github_user,
                github_repo,
                github_sender
            ):
                logger.info(
                    "%s is not a collaborator of this repo", github_sender
                )
                return (
                    "User is not a collaborator of this repo. "
                    "Please start demo manually."
                )
        except GitHubError as ge:
            # If user does not have permission to check repo collaborators
            # an exception with the 403 code is expected.
            if 403 == ge.code:
                gh = login('-', password=settings.GITHUB_TOKEN)
                bot = gh.user().login
                return (
                    "User {bot} does not have enough permissions "
                    "to perform necessary checks. "
                    "Please review user permissions for this repository."
                ).format(bot=bot)
            return "There was a GitHub API error."

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

    p = Popen(['git', 'reset', '--hard', 'HEAD'], cwd=local_path)
    p.wait()

    # Check for the run command to continue
    if not os.path.exists(run_command_path):
        message = 'No ./run found. Unable to start demo.'
        logger.info(message)
        return message

    # Check the project has the minimum required version of ./run
    run_script_version = (
        check_output(["./run", "--version"], cwd=local_path)
        .decode("utf-8")
        .rstrip()
        .split("@")[-1]
    )

    if StrictVersion(run_script_version) < StrictVersion(MIN_RUNSCRIPT_VERSION):
        message = (
            "Unable to start demo. Minimum required "
            "version of ./run script is {}"
        ).format(MIN_RUNSCRIPT_VERSION)
        logger.info(message)
        return message

    # Stop bower complaining about running as root...
    # This actually updates the run command for now and resets on rerun
    run_file_contents = open(run_command_path).read()
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
    demo_url_full = ''.join(['https://', demo_url, '/'])
    if demo_url_path:
        demo_url_full = ''.join([demo_url_full, demo_url_path, '/'])
    logger.info('Starting demo: %s', demo_url_full)

    port = _get_open_port()

    docker_options = ''
    docker_labels = {
        'traefik.enable': 'true',
        'traefik.frontend.rule': 'Host:{url}'.format(url=demo_url),
        'traefik.port': port,
        'run.demo': True,
        'run.demo.url': demo_url,
        'run.demo.url_full': demo_url_full,
        'run.demo.github_user': github_user,
        'run.demo.github_repo': github_repo,
        'run.demo.github_pr': github_pr,
        'run.demo.vcs_provider': "github"
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
        return False

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


def start_launchpad_demo(
    demo_url,
    user,
    repo,
    branch,
    pr,
    context=None
):
    logger = logging.getLogger(__name__)

    # Check is the user is member of any of the allowed teams
    logger.info('Verifying if user is in allowed teams')
    team_member = False
    for team in settings.LAUNCHPAD_ALLOWED_TEAMS:
        if _is_launchpad_team_member(team, user):
            team_member = True
            break

    if not team_member:
        logger.error(
            "User is not a member of any of the allowed teams (%s)",
            settings.LAUNCHPAD_ALLOWED_TEAMS
        )
        return False

    os.makedirs(settings.DEMO_DIR, exist_ok=True)
    local_path = os.path.join(settings.DEMO_DIR, demo_url)

    # Create docker client
    client = docker.from_env()

    # Clone or update branch
    if not os.path.isdir(local_path):
        clone_url = "https://git.launchpad.net/{user}/{repo}/".format(
            user=user,
            repo=repo,
        )

        logger.info("Cloning git repo: %s", clone_url)
        p = Popen(["git", "clone", clone_url, local_path])
        return_code = p.wait()
        if return_code > 0:
            logger.error("Error while cloning %s", clone_url)
            return False
        logger.info("Checking out feature branch %s", branch)
        p = Popen(["git", "checkout", branch], cwd=local_path)
        return_code = p.wait()
        if return_code > 0:
            logger.error("Error while checkint out branch: %s", branch)
            return False
    else:
        # Docker cleanup
        logger.info("Running docker cleanup")
        try:
            container = client.containers.get(demo_url)
            container.stop()
            container.remove(v=True)
            client.images.remove(image=demo_url)
        except Exception as e:
            logger.error(e)

        # Pull latest changes on source branch
        logger.info("Pulling latest changes for branch: %s", branch)
        p = Popen(["git", "pull"], cwd=local_path)
        return_code = p.wait()
        if return_code > 0:
            logger.error(
                "Error while fetching latest changes for branch: %s",
                branch
            )
            return False

    # Docker build
    logger.info("Building image %s", demo_url)
    try:
        docker_file = None
        docker_file_path = "{}/Dockerfile".format(local_path)
        if not os.path.exists(docker_file_path):
            url = settings.DOCKERFILE_REPO_TEMPLATE.format(
                "launchpad",
                repo,
                "Dockerfile"
            )
            response = urllib.request.urlopen(url)
            data = response.read().decode("utf-8")
            open(docker_file_path, "w").write(data)

        client.images.build(
            path=local_path,
            tag=demo_url,
            rm=True,
        )
    except Exception as e:
        logger.info("Error building image: %s", e)
        return False

    # Docker start
    logger.info("Starting container %s", demo_url)

    # TODO: Make port allocation dynamic
    # For now expose 5240 if maas or 80 if any other project
    ports = {}
    port = _get_open_port()
    if repo == "maas":
        ports[5240] = port
    else:
        ports[80] = port

    # TODO: Fix views  and templates so we don't have to start
    # launchpad demos with github prefixed labels.
    docker_labels = {
        "traefik.enable": "true",
        "traefik.frontend.rule": "Host:{url}".format(url=demo_url),
        "traefik.port": str(port),
        "run.demo": "True",
        "run.demo.url": demo_url,
        "run.demo.url_full": "http://{}".format(demo_url),
        "run.demo.github_user": user,
        "run.demo.github_repo": repo,
        "run.demo.github_pr": pr,
        "run.demo.vcs_provider": "launchpad",
    }

    try:
        client.containers.run(
            demo_url,
            name=demo_url,
            ports=ports,
            labels=docker_labels,
            detach=True
        )
    except Exception as e:
        logger.info("Error starting the container %s", e)
        return False

    message = "Starting demo at: {demo_url}".format(demo_url=demo_url)
    logger.info(message)
    return message


def stop_launchpad_demo(
    demo_url,
    context=None
):
    logger = logging.getLogger(__name__)
    logger.info("Stopping demo: %s", demo_url)

    # Create docker client
    client = docker.from_env()
    try:
        container = client.containers.get(demo_url)
        container.stop()
        container.remove(v=True)
        client.images.remove(image=demo_url)
    except Exception as e:
        logger.error(e)
        return False

    local_path = os.path.join(settings.DEMO_DIR, demo_url)
    if not os.path.isdir(local_path):
        return False

    logger.info("Deleting files for %s", demo_url)
    shutil.rmtree(local_path)
    logger.info("Demo %s removed.", demo_url)
