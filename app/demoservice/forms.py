from django import forms

from demoservice.tasks import (
    queue_start_demo,
    queue_stop_demo,
)


class DemoStartForm(forms.Form):
    github_user = forms.CharField(
        label="GitHub Organization",
    )
    github_repo = forms.CharField(
        label="GitHub Repository",
    )
    github_pr = forms.IntegerField(
        label="GitHub pull request ID",
    )
    github_notify = forms.BooleanField(
        label="Notify inside GitHub pull request (new comment)",
        required=False,
    )

    def start_demo(self):
        queue_start_demo(
            github_user=self.cleaned_data['github_user'],
            github_repo=self.cleaned_data['github_repo'],
            github_pr=self.cleaned_data['github_pr'],
            send_github_notification=self.cleaned_data['github_notify'],
        )
        return True


class DemoStopForm(forms.Form):
    github_user = forms.CharField(
        label="GitHub Organization",
    )
    github_repo = forms.CharField(
        label="GitHub Repository",
    )
    github_pr = forms.IntegerField(
        label="GitHub pull request ID",
    )

    def stop_demo(self):
        queue_stop_demo(
            github_user=self.cleaned_data['github_user'],
            github_repo=self.cleaned_data['github_repo'],
            github_pr=self.cleaned_data['github_pr'],
        )
        return True
