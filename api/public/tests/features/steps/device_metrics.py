import json
import uuid
from http import HTTPStatus
from unittest import mock
from unittest.mock import patch, MagicMock, call

from behave import when, then
from hamcrest import assert_that, equal_to

payload = dict(
    type='timing',
    start='123'
)


@when('the metric is sent')
@patch('public_api.endpoints.device_metrics.MetricsService')
def send_metric(context, metrics_service):
    context.client_config['METRICS_SERVICE'] = metrics_service
    device_id = context.device_login['uuid']
    context.response = context.client.post(
        '/device/{uuid}/metric/{metric}'.format(uuid=device_id, metric='timing'),
        data=json.dumps(payload),
        content_type='application_json'
    )


@then('200 status code should be returned')
def validate_response(context):
    response = context.response
    assert_that(response.status_code, equal_to(HTTPStatus.OK))
    metrics_service: MagicMock = context.client_config['METRICS_SERVICE']
    metrics_service.send_metric.assert_has_calls([
        call('timing',
        context.account.id,
        context.device_login['uuid'],
        mock.ANY)
    ])


@when('the metric is sent by an invalid device')
@patch('public_api.endpoints.device_metrics.MetricsService')
def send_metrics_invalid(context, metrics_service):
    context.client_config['METRICS_SERVICE'] = metrics_service
    context.response = context.client.post(
        '/device/{uuid}/metric/{metric}'.format(uuid=str(uuid.uuid4()), metric='timing'),
        data=json.dumps(payload),
        content_type='application_json'
    )


@then('metrics endpoint should return 204')
def validate_invalid_device(context):
    response = context.response
    assert_that(response.status_code, equal_to(HTTPStatus.NO_CONTENT))
    metrics_service: MagicMock = context.client_config['METRICS_SERVICE']
    metrics_service.send_metric.assert_not_called()
