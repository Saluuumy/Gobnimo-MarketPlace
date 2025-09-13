import json

with open('cleaned_local_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    if item['model'] == 'base.user':
        item['fields'].pop('first_name', None)
        item['fields'].pop('last_name', None)

with open('cleaned_local_data_no_name.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)

print("✅ Cleaned file saved as cleaned_local_data_no_name.json")
