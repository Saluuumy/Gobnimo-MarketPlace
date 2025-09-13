import json

# Adjust these to match your model fields
NUMERIC_FIELDS = ['price', 'quantity', 'rating']  # Add your numeric fields
TEXT_FIELDS = ['description', 'name', 'title']    # Add your text fields

with open('cleaned_final.json', 'r') as f:
    data = json.load(f)

for entry in data:
    if 'fields' in entry:
        # Fix numeric fields
        for field in NUMERIC_FIELDS:
            if field in entry['fields']:
                # Handle empty strings
                if entry['fields'][field] == '':
                    entry['fields'][field] = None
                # Handle numeric strings
                elif isinstance(entry['fields'][field], str) and entry['fields'][field].replace('.', '', 1).isdigit():
                    if '.' in entry['fields'][field]:
                        entry['fields'][field] = float(entry['fields'][field])
                    else:
                        entry['fields'][field] = int(entry['fields'][field])
        
        # Fix text fields
        for field in TEXT_FIELDS:
            if field in entry['fields'] and entry['fields'][field]:
                # Remove non-ASCII characters
                cleaned = ''.join(c for c in entry['fields'][field] if ord(c) < 128)
                entry['fields'][field] = cleaned

with open('railway_ready.json', 'w') as f:
    json.dump(data, f, indent=2)