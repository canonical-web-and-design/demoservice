import docker
import hashlib
import hmac
import http
import json
import logging
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView

from demoservice.forms import DemoStartForm, DemoStopForm
from demoservice.libs.github import handle_webhook

logger = logging.getLogger(__name__)


def demo_index(request):
    docker_client = docker.from_env()
    running_demos = docker_client.containers.list(
        filters={
            'status': 'running',
            'label': 'run.demo',
        }
    )
    return HttpResponse(running_demos)


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
            if demo not in demos:
                demos.append(demo)
        return demos

    def get_context_data(self, **kwargs):
        context = super(DemoIndexView, self).get_context_data(**kwargs)
        context['demos'] = self._get_running_demos()
        return context


class DemoStartView(FormView):
    template_name = 'demo_start.html'
    form_class = DemoStartForm
    success_url = '/'

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super().get_initial()
        initial['github_user'] = 'canonical-websites'
        return initial

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        is_demo_starting = form.start_demo()
        if is_demo_starting:
            messages.success(self.request, 'Demo starting...')
        return super(DemoStartView, self).form_valid(form)


class DemoStopView(FormView):
    template_name = 'demo_stop.html'
    form_class = DemoStopForm
    success_url = '/'

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super().get_initial()
        initial['github_user'] = 'canonical-websites'
        return initial

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        is_demo_stopping = form.stop_demo()
        if is_demo_stopping:
            messages.success(self.request, 'Demo stopping...')
        return super(DemoStopView, self).form_valid(form)


@csrf_exempt
def github_webhook(request):
    """ https://gist.github.com/grantmcconnaughey/6169d8b7a2e770e85c5617bc80ed00a9
    """
    # Check the X-Hub-Signature header to make sure this is a valid request.
    logger.debug('Receiving GitHub webook. Verifying signature.')
    github_signature = request.META.get(
        'HTTP_X_HUB_SIGNATURE', None
    )
    if not github_signature:
        logger.debug('Missing HTTP_X_HUB_SIGNATURE HTTP header')
        return HttpResponseForbidden('Missing signature header')
    signature = hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode('ascii'),
        request.body,
        hashlib.sha1
        )
    expected_signature = 'sha1=' + signature.hexdigest()
    if not hmac.compare_digest(github_signature, expected_signature):
        logger.debug('Invalid webhook signature.')
        return HttpResponseForbidden('Invalid signature header')

    # Sometimes the payload comes in as the request body, sometimes it comes in
    # as a POST parameter. This will handle either case.
    if 'payload' in request.POST:
        payload = json.loads(request.POST['payload'].decode("utf8"))
    else:
        payload = json.loads(request.body.decode("utf8"))

    event = request.META['HTTP_X_GITHUB_EVENT']

    handle_webhook(event, payload)

    return HttpResponse('Webhook received', status=http.HTTPStatus.ACCEPTED)
