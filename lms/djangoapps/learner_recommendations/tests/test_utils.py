""" Test Recommendations helpers methods """
import ddt
from django.test import TestCase
from unittest.mock import Mock, patch

from common.djangoapps.student.tests.factories import (
    CourseEnrollmentFactory,
    UserFactory,
)
from lms.djangoapps.learner_recommendations.utils import (
    _has_country_restrictions,
    filter_recommended_courses,
    get_amplitude_course_recommendations,
)
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


@ddt.ddt
class TestRecommendationsHelper(TestCase):
    """Test course recommendations helper methods."""

    def setUp(self):
        super().setUp()
        self.user = UserFactory()

    @ddt.data(
        ({}, 0),
        ({"userData": {}}, 0),
        ({"userData": {"recommendations": []}}, 0),
        (
            {
                "userData": {
                    "recommendations": [
                        {
                            "items": ["MITx+6.00.1x", "IBM+PY0101EN", "HarvardX+CS50P"],
                            "is_control": True,
                            "has_is_control": False,
                        }
                    ],
                }
            },
            3,
        ),
    )
    @patch("lms.djangoapps.learner_recommendations.utils.requests.get")
    @ddt.unpack
    def test_get_amplitude_course_recommendations_method(
        self, mocked_response, expected_recommendations_count, mock_get
    ):
        """
        Tests the get_amplitude_recommendations method returns course key list.
        """
        mock_get.return_value = Mock(status_code=200, json=lambda: mocked_response)
        _, _, course_keys = get_amplitude_course_recommendations(
            self.user.id, "amplitude-rec-id"
        )
        self.assertEqual(len(course_keys), expected_recommendations_count)

    @ddt.data(
        ({}, False),
        ({"restriction_type": "blocklist", "countries": []}, False),
        ({"restriction_type": "blocklist", "countries": ["SA"]}, False),
        ({"restriction_type": "blocklist", "countries": ["US"]}, True),
        ({"restriction_type": "allowlist", "countries": []}, False),
        ({"restriction_type": "allowlist", "countries": ["SA"]}, True),
        ({"restriction_type": "allowlist", "countries": ["US"]}, False),
    )
    @ddt.unpack
    def test_has_country_restrictions_method(
        self,
        location_restriction,
        expected_response,
    ):
        """
        Helper method to test the _has_country_restrictions method.
        """
        product = {"location_restriction": location_restriction}
        assert _has_country_restrictions(product, "US") == expected_response


class TestFilterRecommendedCourses(ModuleStoreTestCase):
    """Test for filter_recommended_courses helper method."""

    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.unrestricted_course_keys = [
            "MITx+6.00.1x",
            "IBM+PY0101EN",
        ]
        self.recommended_course_keys = [
            "MITx+6.00.1x",
            "IBM+PY0101EN",
            "HarvardX+CS50P",
            "UQx+IELTSx",
            "HarvardX+CS50x",
            "Harvard+CS50z",
            "BabsonX+EPS03x",
            "TUMx+QPLS2x",
            "NYUx+FCS.NET.1",
            "MichinX+101x",
        ]
        self.course_run_keys = [
            "course-v1:MITx+6.00.1x+Run_0",
            "course-v1:IBM+PY0101EN+Run_0",
            "course-v1:HarvardX+CS50P+Run_0",
            "course-v1:UQx+IELTSx+Run_0",
            "course-v1:HarvardX+CS50x+Run_0",
            "course-v1:Harvard+CS50z+Run_0",
            "course-v1:BabsonX+EPS03x+Run_0",
            "course-v1:TUMx+QPLS2x+Run_0",
            "course-v1:NYUx+FCS.NET.1+Run_0",
            "course-v1:MichinX+101x+Run_0",
        ]
        self.course_keys_with_active_course_runs = [
            "MITx+6.00.1x",
            "IBM+PY0101EN",
            "HarvardX+CS50P",
            "UQx+IELTSx",
            "HarvardX+CS50x",
            "Harvard+CS50z",
            "BabsonX+EPS03x",
            "TUMx+QPLS2x",
        ]
        self.enrolled_course_run_keys = [
            "course-v1:HarvardX+CS50x+Run_0",
            "course-v1:Harvard+CS50z+Run_0",
            "course-v1:BabsonX+EPS03x+Run_0",
            "course-v1:TUMx+QPLS2x+Run_0",
            "course-v1:NYUx+FCS.NET.1+Run_0",
            "course-v1:MichinX+101x+Run_0",
        ]

    def _mock_get_course_data(self, course_id, fields=None, querystring=None):  # pylint: disable=unused-argument
        """
        Mocked response for the get_course_data call
        """
        course_data = {
            "course_key": course_id,
            "title": "Mocked course title",
            "owners": [{"logo_image_url": "https://www.logo_image_url.com"}],
            "marketing_url": "https://www.marketing_url.com",
        }

        if course_id not in self.unrestricted_course_keys:
            course_data.update(
                {
                    "location_restriction": {
                        "restriction_type": "blocklist",
                        "countries": ["US"],
                    }
                }
            )

        if course_id in self.course_keys_with_active_course_runs:
            course_data.update(
                {
                    "course_runs": [
                        {
                            "key": "course-v1:MITx+6.00.1x+Run_0",
                        }
                    ]
                }
            )

        return course_data

    @patch("lms.djangoapps.learner_recommendations.utils.get_course_data")
    def test_enrolled_courses_are_removed_from_recommendations(
        self, mocked_get_course_data
    ):
        """
        Tests that given a recommended course list, the filter_recommended_courses
        method removes the enrolled courses from it.
        """
        total_enrolled_courses = len(self.enrolled_course_run_keys)
        total_recommendations = len(self.recommended_course_keys)
        mocked_get_course_data.side_effect = self._mock_get_course_data
        for course_run_key in self.enrolled_course_run_keys:
            CourseEnrollmentFactory(course_id=course_run_key, user=self.user)

        filtered_courses = filter_recommended_courses(
            self.user, self.recommended_course_keys, total_recommendations
        )
        assert len(filtered_courses) == (total_recommendations - total_enrolled_courses)

    @patch("lms.djangoapps.learner_recommendations.utils.get_course_data")
    def test_request_course_is_removed_from_the_recommendations(
        self,
        mocked_get_course_data,
    ):
        """
        Test that if the "request course" is one of the recommended courses,
        we filter that from the final recommendation list.
        """
        request_course = self.recommended_course_keys[0]
        mocked_get_course_data.side_effect = self._mock_get_course_data
        filtered_courses = filter_recommended_courses(
            self.user,
            self.recommended_course_keys,
            request_course=request_course,
        )

        assert all(course["course_key"] != request_course for course in filtered_courses) is True

    @patch("lms.djangoapps.learner_recommendations.utils.get_course_data")
    def test_country_restrictions_for_the_recommended_course(
        self,
        mocked_get_course_data,
    ):
        """
        Test that if a recommended course is restricted in the country the user
        is logged from, the course is filtered out.
        """
        mocked_get_course_data.side_effect = self._mock_get_course_data
        filtered_courses = filter_recommended_courses(
            self.user, self.recommended_course_keys, user_country_code="US"
        )
        expected_recommendations = []
        for course_key in self.unrestricted_course_keys:
            expected_recommendations.append(self._mock_get_course_data(course_key))

        assert filtered_courses == expected_recommendations

    @patch("lms.djangoapps.learner_recommendations.utils.get_course_data")
    def test_recommend_only_active_courses(
        self,
        mocked_get_course_data,
    ):
        """
        Test that courses having no active course runs are filtered out from recommended courses.
        """
        mocked_get_course_data.side_effect = self._mock_get_course_data
        filtered_courses = filter_recommended_courses(
            self.user, self.recommended_course_keys
        )
        expected_recommendations = []
        for course_key in self.course_keys_with_active_course_runs:
            expected_recommendations.append(self._mock_get_course_data(course_key))

        assert filtered_courses == expected_recommendations
