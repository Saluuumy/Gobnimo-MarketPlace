import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Ecommerce.settings')
django.setup()

from django.db import connections, transaction
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.hashers import make_password

# Define the transfer order to respect model dependencies
MODEL_ORDER = [
    ('base', 'User'),          # Must come first (referenced by others)
    ('base', 'Category'),       # Referenced by Ad
    ('base', 'Ad'),             # Referenced by most models
    ('base', 'AdImage'),        # Depends on Ad
    ('base', 'Comment'),        # Depends on User and Ad
    ('base', 'FeaturedAd'),     # Depends on Ad
    ('base', 'FeaturedAdHistory'), # Depends on Ad
    ('base', 'PendingFeaturedAd'), # Depends on Ad
    ('base', 'Notification'),   # Depends on User and Ad
]

def transfer_data():
    for app_label, model_name in MODEL_ORDER:
        model = ContentType.objects.get(app_label=app_label, model=model_name.lower()).model_class()
        table_name = model._meta.db_table
        print(f"\nTransferring {table_name}...")
        
        # Get SQLite data
        with connections['old_sqlite'].cursor() as cursor:
            cursor.execute(f"SELECT * FROM {table_name}")
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            print(f"Found {len(rows)} records")
        
        # Special handling for User model passwords
        if model_name == 'User':
            for i, row in enumerate(rows):
                row_dict = dict(zip(columns, row))
                # Convert password to Django format if needed
                if not row_dict['password'].startswith(('pbkdf2_', 'bcrypt$', 'argon2')):
                    rows[i] = tuple(
                        make_password(row_dict['password']) if col == 'password' else val 
                        for col, val in zip(columns, row)
                    )
        
        # Insert into PostgreSQL
        if rows:
            with connections['default'].cursor() as cursor:
                placeholders = ', '.join(['%s'] * len(columns))
                columns_str = ', '.join(columns)
                
                try:
                    with transaction.atomic():
                        # Batch insert for better performance
                        batch_size = 100
                        for i in range(0, len(rows), batch_size):
                            batch = rows[i:i+batch_size]
                            cursor.executemany(
                                f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})",
                                batch
                            )
                        print(f"Inserted {len(rows)} records")
                except Exception as e:
                    print(f"Error transferring {table_name}: {e}")
                    # Print first problematic row for debugging
                    if rows:
                        print(f"Sample row: {rows[0]}")

if __name__ == '__main__':
    print("Starting data migration...")
    transfer_data()
    print("\nData transfer complete!")
    print("Run sequence reset command next:")
    print("python manage.py sqlsequencereset your_app | python manage.py dbshell")