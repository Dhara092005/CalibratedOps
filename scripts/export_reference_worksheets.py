"""Export pending reference worksheets without submitting any human review.

Run prepare_research_materials.py first. These files reveal reference answers;
give them to reviewers, never to unfamiliar study participants.
"""
import argparse
import json
from pathlib import Path


def export(materials):
    materials = Path(materials)
    queue = json.loads((materials / 'reference-review-queue.json').read_text(encoding='utf-8'))
    destination = materials / 'reviewer-only'
    destination.mkdir(parents=True, exist_ok=True)
    pending = [row for row in queue if row['recovery_status'] != 'accepted']
    for row in pending:
        lines = [f"# Reference review: {row['record_id']}", '',
                 'REVIEWER ONLY: contains proposed reference answers. Do not show to participants.', '',
                 f"Dataset: {row['dataset_name']} ({row['dataset_id']})",
                 f"Split: {row['split']}; current recovery revision: {row['recovery_revision']}", '',
                 f"Source: {row['source_url']}", f"Locate: {row['source_locator']}",
                 f"Unresolved date: {row['date_unresolved']}", '',
                 '## Provisional proposal', '',
                 'Assistant-authored material awaiting human assessment; not an accepted reference.', '']
        for number, step in enumerate((row['draft'] or {}).get('steps', []), 1):
            lines += [f"{number}. {step['action']}: {step['description']}",
                      f"   Declared prerequisites: {step['requires']}"]
        lines += ['', 'Draft scope/explanation:', (row['draft'] or {}).get('explanation', ''), '',
                  '## Human reviewer completes', '',
                  '- Reviewer and relevant experience: [not yet supplied]',
                  '- Review date: [not yet supplied]',
                  '- Read the original report and check the incident identity/date.',
                  '- Identify source passages supporting each action and dependency.',
                  '- Distinguish immediate mitigation from later preventive work.',
                  '- Check missing actions, unsupported extras, and alternative valid orderings.',
                  '- Decision: [accept / revise / flag; not yet supplied]',
                  '- Source-based rationale and uncertainties: [not yet supplied]', '',
                  'Save the actual human decision in Label review > select this dataset and incident > Review recovery.',
                  'This worksheet alone does not update the app or establish independent acceptance.', '']
        (destination / f"{row['record_id']}.md").write_text('\n'.join(lines), encoding='utf-8')
    index = ['# Pending reference worksheets', '',
             f'{len(pending)} pending references. No human decisions were created.', '',
             'Reviewer-only materials: keep separate from participant instructions.', '']
    index += [f"- [{row['record_id']}]({row['record_id']}.md)" for row in pending]
    (destination / 'INDEX.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    print(f'Exported {len(pending)} pending worksheets to {destination.resolve()}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--materials', default='runs/research-materials')
    export(parser.parse_args().materials)
