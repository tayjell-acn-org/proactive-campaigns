import sqlite3
from datetime import datetime, UTC

conn = sqlite3.connect("campaign.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS AccountContactHistory
(
    ContactHistoryId INTEGER PRIMARY KEY AUTOINCREMENT,

    CampaignCode TEXT NOT NULL,
    Ban TEXT NOT NULL,

    ChannelType TEXT NOT NULL,           -- EMAIL, SMS
    ContactValue TEXT,                   -- email address or phone number

    Status TEXT NOT NULL,                -- CONTACTED, SUPPRESSED, EXCLUDED, FAILED
    ReasonCode TEXT,                     -- RECENT_CAMPAIGN_CONTACT, INVALID_PHONE, etc.

    NotifyNowTransactionId TEXT,

    ContactDate TEXT NOT NULL,
    CreatedDate TEXT NOT NULL
);
""")

conn.commit()
conn.close()

print("Table created successfully")
