from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from results.models import Result
from tasks.models import Task

from .models import Rule


class RuleDeleteTests(APITestCase):
    def test_delete_keeps_historical_result_and_hides_rule(self):
        rule = Rule.objects.create(
            rule_id='duplicate-charge-1',
            drug_name='静脉注射',
            description='重复收费测试规则',
            type='重复收费',
            status=True,
        )
        task = Task.objects.create(
            name='重复收费测试任务',
            hospitalization_ids=['case-1'],
        )
        result = Result.objects.create(
            task=task,
            rule=rule,
            hospitalization_id='case-1',
        )

        response = self.client.delete(reverse('rule-detail', args=[rule.pk]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        rule.refresh_from_db()
        self.assertTrue(rule.is_deleted)
        self.assertFalse(rule.status)
        self.assertTrue(Result.objects.filter(pk=result.pk, rule=rule).exists())

        list_response = self.client.get(
            reverse('rule-list'),
            {'type': '重复收费'},
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 0)
