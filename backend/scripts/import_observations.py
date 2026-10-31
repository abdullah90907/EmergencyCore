"""Import operator-curated historical evidence; never infer closures from a PDF."""
import argparse
import csv
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emergencycore import create_app
from emergencycore.services.simulation import observe
from emergencycore.database import get_db

parser = argparse.ArgumentParser()
parser.add_argument('scenario_id')
parser.add_argument('csv_file', type=Path)
parser.add_argument('--reviewed', action='store_true', help='Operator attests evidence and edge mappings were checked')
args = parser.parse_args()
app = create_app()
with app.app_context():
    rows = list(csv.DictReader(args.csv_file.open(encoding='utf-8-sig', newline='')))
    with get_db():
        for row in rows:
            row['reviewed'] = args.reviewed
            row['evidence'] = row.get('evidence') or 'Official'
            result = observe(args.scenario_id, row, trusted=True, commit=False)
            print(result['id'])
