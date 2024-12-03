-- Drop existing tables
DROP TABLE IF EXISTS chatbot_chatmessage;
DROP TABLE IF EXISTS chatbot_conversation;

-- Remove migration records
DELETE FROM django_migrations WHERE app = 'chatbot' AND name IN ('0005_chatmessage_conversation', '0006_auto_20241201_2347');
