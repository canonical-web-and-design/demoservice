import docker
import hashlib
import hmac
import http
import json
import logging
from operator import itemgetter
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from demoservice.forms import DemoStartForm, DemoStopForm
from demoservice.libs.github import handle_webhook
from demoservice.libs.launchpad import handle_webhook as handle_launchpad_webhook

DEFAULT_VCS_USER = 'canonical-websites'
logger = logging.getLogger(__name__)


def _get_github_url(demo):
    url = ''
    if demo['github_branch']:
        url = 'https://github.com/{user}/{repo}/tree/{branch}'.format(
            user=demo['github_user'],
            repo=demo['github_repo'],
            branch=demo['github_branch'],
        )
    if demo['github_pr']:
        url = 'https://github.com/{user}/{repo}/pull/{id}'.format(
            user=demo['github_user'],
            repo=demo['github_repo'],
            id=demo['github_pr'],
        )
    return url


class DemoIndexView(TemplateView):
    template_name = 'demo_index.html'

    def _get_running_demos(self,):
        docker_client = docker.from_env()
        demo_containers = docker_client.containers.list(
            filters={
                'status': 'running',
                'label': 'run.demo',
            }
        )
        demos = []
        for container in demo_containers:
            labels = container.labels
            url = labels.get('run.demo.url', '')
            url_full = labels.get('run.demo.url_full', url)
            demo = {
                'name': container.name,
                'url': url,
                'url_full': url_full,
                'github_user': labels.get('run.demo.github_user', ''),
                'github_repo': labels.get('run.demo.github_repo', ''),
                'github_branch': labels.get('run.demo.github_branch', ''),
                'github_pr': labels.get('run.demo.github_pr', ''),
            }
            demo['github_url'] = _get_github_url(demo)
            is_duplicate_demo = any(
                _demo['url'] == url for _demo in demos
            )
            if not is_duplicate_demo:
                demos.append(demo)
        demos.sort(key=itemgetter('url'))
        return demos

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['demos'] = self._get_running_demos()
        return context


class DemoStartView(FormView):
    template_name = 'demo_form.html'
    form_class = DemoStartForm
    success_url = '/'

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super().get_initial()
        params = self.request.GET

        url = params.get('url')
        if url:
            initial['github_url'] = url
        else:
            initial['github_pr'] = params.get('pr', '')
            initial['github_repo'] = params.get('repo', '')
            initial['github_user'] = params.get('user', DEFAULT_VCS_USER)

        return initial

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        is_demo_starting = form.start_demo()
        if is_demo_starting:
            messages.success(self.request, 'Demo starting...')
        return super(DemoStartView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_name"] = "Start or update a demo"
        context["form_action"] = reverse("demo_start")
        return context


class DemoStopView(FormView):
    template_name = 'demo_form.html'
    form_class = DemoStopForm
    success_url = '/'

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super().get_initial()
        params = self.request.GET

        url = params.get('url')
        if url:
            initial['github_url'] = url
        else:
            initial['github_pr'] = params.get('pr', '')
            initial['github_repo'] = params.get('repo', '')
            initial['github_user'] = params.get('user', DEFAULT_VCS_USER)

        return initial

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        is_demo_stopping = form.stop_demo()
        if is_demo_stopping:
            messages.success(self.request, 'Demo stopping...')
        return super(DemoStopView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_name'] = "Stop a demo"
        context["form_action"] = reverse("demo_stop")
        return context


def _validate_webhook_signature(request, remote_signature, webhook_secret):
    """ Validate webhook is legit using X_HUB_SIGNATURE"""
    if not remote_signature:
        logger.debug('Missing HTTP_X_HUB_SIGNATURE HTTP header')
        return False
    signature = hmac.new(
        webhook_secret.encode('ascii'),
        request.body,
        hashlib.sha1
    )
    expected_signature = 'sha1=' + signature.hexdigest()
    if not hmac.compare_digest(remote_signature, expected_signature):
        logger.debug('Invalid webhook signature.')
        return False

    return True


@csrf_exempt
def github_webhook(request):
    """ https://gist.github.com/grantmcconnaughey/6169d8b7a2e770e85c5617bc80ed00a9
    """
    # Check the X-Hub-Signature header to make sure this is a valid request.
    logger.debug('Receiving GitHub webook. Verifying signature.')
    github_signature = request.META.get(
        'HTTP_X_HUB_SIGNATURE', None
    )

    if not settings.DEBUG and not _validate_webhook_signature(
        request,
        github_signature,
        settings.GITHUB_WEBHOOK_SECRET
    ):
        return HttpResponseForbidden('Invalid webook signature')

    # Sometimes the payload comes in as the request body, sometimes it comes in
    # as a POST parameter. This will handle either case.
    if 'payload' in request.POST:
        payload = json.loads(request.POST['payload'].decode("utf8"))
    else:
        payload = json.loads(request.body.decode("utf8"))

    event = request.META['HTTP_X_GITHUB_EVENT']

    handle_webhook(event, payload)

    return HttpResponse('Webhook received', status=http.HTTPStatus.ACCEPTED)


@csrf_exempt
def launchpad_webhook(request):
    """ https://gist.github.com/grantmcconnaughey/6169d8b7a2e770e85c5617bc80ed00a9
    """
    # Check the X-Hub-Signature header to make sure this is a valid request.
    logger.debug('Receiving Launchpad webook. Verifying signature.')

    launchpad_signature = request.META.get(
        'HTTP_X_HUB_SIGNATURE', None
    )

    if not settings.DEBUG and not _validate_webhook_signature(
        request,
        launchpad_signature,
        settings.LAUNCHPAD_WEBHOOK_SECRET
    ):
        return HttpResponseForbidden('Invalid webook signature')

    # Sometimes the payload comes in as the request body, sometimes it comes in
    # as a POST parameter. This will handle either case.
    if 'payload' in request.POST:
        payload = json.loads(request.POST['payload'].decode("utf8"))
    else:
        payload = json.loads(request.body.decode("utf8"))

    event = request.META['HTTP_X_LAUNCHPAD_EVENT_TYPE']

    handle_launchpad_webhook(event, payload)

    return HttpResponse('Webhook received', status=http.HTTPStatus.ACCEPTED)
