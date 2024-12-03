import sqlite3

# Connect to the database
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Execute SQL commands
cursor.execute('DROP TABLE IF EXISTS chatbot_chatmessage')
cursor.execute('DROP TABLE IF EXISTS chatbot_conversation')
cursor.execute("DELETE FROM django_migrations WHERE app = 'chatbot' AND name IN ('0005_chatmessage_conversation', '0006_auto_20241201_2347')")

# Commit changes and close connection
conn.commit()
conn.close()
print("Database tables cleaned successfully")
