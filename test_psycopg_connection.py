import psycopg
import os
from dotenv import load_dotenv

load_dotenv()   # .env 파일 읽기

conn = psycopg.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT 1;")
print(cur.fetchone())
conn.close()

