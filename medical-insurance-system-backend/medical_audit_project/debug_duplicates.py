
import os
import django
import sys
import json

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_audit_project.settings')
django.setup()

from results.models import Result
from tasks.models import Task

def debug_task_details(task_id):
    print(f"\n--- Debugging Task {task_id} Details ---")
    results = Result.objects.filter(task_id=task_id).order_by('id')
    count = results.count()
    print(f"Total Results: {count}")
    
    for i, r in enumerate(results):
        print(f"\n[Result {i+1}] ID: {r.id}")
        print(f"  Rule: {r.rule.rule_id if r.rule else 'None'}")
        print(f"  Reason: {r.reason}")
        print(f"  Violation Item (Raw): {r.violation_item!r}")
        
    # Check distinctness manually
    seen = set()
    dups = 0
    for r in results:
        # Create a tuple of the fields used for deduplication
        key = (r.task_id, r.hospitalization_id, r.rule_id, r.reason, r.violation_item)
        if key in seen:
            print(f"Duplicate found! ID {r.id} matches a previous record.")
            dups += 1
        else:
            seen.add(key)
            
    print(f"\nManual duplicate check found {dups} duplicates.")

debug_task_details(97)
