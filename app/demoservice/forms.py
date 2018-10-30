from django import forms

from demoservice.libs.github import (
    is_valid_github_url,
    get_github_info_from_url,
)
from demoservice.tasks.github import queue_start_demo, queue_stop_demo


class DemoFormMixin(forms.Form):
    github_url = forms.URLField(
        label="GitHub URL",
        required=False,
        help_text="Ex: https://github.com/canonical-webteam/demoservice/pull/36",
    )
    github_user = forms.CharField(label="GitHub Organization", required=False)
    github_repo = forms.CharField(label="GitHub Repository", required=False)
    github_pr = forms.IntegerField(
        label="GitHub pull request ID", required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        github_url = cleaned_data.get("github_url")

        # If we have a GitHub URL, try to extract data from it.
        if github_url:
            if is_valid_github_url(github_url):
                github_info = get_github_info_from_url(github_url)
                cleaned_data["github_pr"] = github_info.get("pr")
                cleaned_data["github_repo"] = github_info.get("repo")
                cleaned_data["github_user"] = github_info.get("user")
            else:
                self.add_error("github_url", "Invalid GitHub URL.")
        else:
            github_pr = cleaned_data.get("github_pr")
            github_repo = cleaned_data.get("github_repo")
            github_user = cleaned_data.get("github_user")

            msg = "This field is required if you don't provide a GitHub URL"
            if not github_pr:
                self.add_error("github_pr", msg)
            if not github_repo:
                self.add_error("github_repo", msg)
            if not github_user:
                self.add_error("github_user", msg)

        return cleaned_data


class DemoStartForm(DemoFormMixin):
    github_notify = forms.BooleanField(
        label="Notify inside GitHub pull request (new comment)", required=False
    )

    def start_demo(self):
        queue_start_demo(
            github_user=self.cleaned_data["github_user"],
            github_repo=self.cleaned_data["github_repo"],
            github_pr=self.cleaned_data["github_pr"],
            send_github_notification=self.cleaned_data["github_notify"],
            github_verify_sender=False,
        )
        return True


class DemoStopForm(DemoFormMixin):
    def stop_demo(self):
        queue_stop_demo(
            github_user=self.cleaned_data["github_user"],
            github_repo=self.cleaned_data["github_repo"],
            github_pr=self.cleaned_data["github_pr"],
        )
        return True
