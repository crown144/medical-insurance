
import os
import django
import sys
import json

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_audit_project.settings')
django.setup()

from results.models import Result
from results.serializers import ResultSerializer
from rules.models import Rule
from tasks.models import Task

def debug_task(task_id):
    print(f"\n--- Debugging Task {task_id} ---")
    results = Result.objects.filter(task_id=task_id)
    count = results.count()
    print(f"Total Results in DB for Task {task_id}: {count}")
    
    if count == 0:
        return

    # Check first result
    r = results.first()
    print(f"Result ID: {r.id}")
    print(f"Hospitalization ID: {r.hospitalization_id}")
    print(f"Violation Item (DB): {r.violation_item!r}")
    print(f"Reason: {r.reason}")
    
    if r.rule:
        print(f"Rule ID: {r.rule.id}")
        print(f"Rule Code: {r.rule.rule_id}")
        print(f"Rule Drug Name: {r.rule.drug_name!r}")
        print(f"Rule Type: {r.rule.type}")
    else:
        print("Rule is None!")

    # Check Serializer Output
    serializer = ResultSerializer(r)
    data = serializer.data
    print("Serialized Data (Partial):")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    # Check for duplicates in DB
    print("\nChecking for potential duplicates in DB:")
    # Group by the fields used in deduplication
    from django.db.models import Count
    dups = results.values('hospitalization_id', 'rule_id', 'reason', 'violation_item').annotate(count=Count('id')).filter(count__gt=1)
    if dups.exists():
        print(f"Found {dups.count()} groups with duplicates.")
        for d in dups:
            print(d)
    else:
        print("No duplicates found based on grouping fields.")

# Try to find the task mentioned
print("Finding tasks...")
tasks = Task.objects.all().order_by('-id')[:5]
for t in tasks:
    print(f"Task: {t.id} - {t.name}")

# Debug the task from the user's message (89) or screenshot (97)
debug_task(97) 
debug_task(89)
