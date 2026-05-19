import json
from common import REG_EXPRESSION_BULGARIAN

def extract_from_json_parse_in_csv(json_path: str, csv_path: str):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
""" TO BE CHECKED
    with open(csv_path, mode='w', encoding='utf-8', newline='') as csvfile:
        fieldnames = ['id', 'number', 'parlMemberId', 'title', 'position', 'text']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for statement in data['statements']:
            cleaned_text = REG_EXPRESSION_BULGARIAN.findall(statement['text'])
            cleaned_text = " ".join(cleaned_text)
            writer.writerow({
                'id': statement['id'],
                'number': statement['number'],
                'parlMemberId': statement['parlMemberId'],
                'title': statement['title'],
                'position': statement['position'],
                'text': cleaned_text
            })
"""