from django.forms import Form
from django.test import SimpleTestCase
from demoservice.forms import DemoFormMixin, DemoStartForm, DemoStopForm
from demoservice.libs.github import (
    is_valid_github_url,
    get_github_info_from_url,
)


class DemoFormMixinTest(SimpleTestCase):
    def test_fields_required_when_no_url_given(self):
        sut = DemoFormMixin({})
        sut.is_valid()

        error_msg = "This field is required if you don't provide a GitHub URL"
        self.assertEqual(3, len(sut.errors))
        self.assertEqual([error_msg], sut.errors.get("github_pr"))
        self.assertEqual([error_msg], sut.errors.get("github_repo"))
        self.assertEqual([error_msg], sut.errors.get("github_user"))

    def test_url_info_overrides_form_data(self):
        self.assertTrue(issubclass(DemoFormMixin, Form))

    def test_extends_form(self):
        self.assertTrue(issubclass(DemoFormMixin, Form))


class StartDemoFormTest(SimpleTestCase):
    def test_extends_demoform_mixin(self):
        self.assertTrue(issubclass(DemoStartForm, DemoFormMixin))


class StopDemoFormTest(SimpleTestCase):
    def test_extends_demoform_mixin(self):
        self.assertTrue(issubclass(DemoStopForm, DemoFormMixin))


class GitHubUtilsTest(SimpleTestCase):
    def test_valid_url(self):
        sut = is_valid_github_url
        self.assertTrue(
            sut("https://github.com/canonical-webteam/demoservice/pull/36")
        )

    def test_get_info_from_url(self):
        sut = get_github_info_from_url
        expected = dict(pr="36", user="canonical-webteam", repo="demoservice")

        result = sut(
            "https://github.com/canonical-webteam/demoservice/pull/36"
        )
        self.assertEqual(expected, result)

    def test_get_info_from_bad_url(self):
        sut = get_github_info_from_url
        expected = None
        result = sut("https://github.com/canonical-webteam/demoservice")
        self.assertEqual(expected, result)
