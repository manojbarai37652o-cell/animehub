import libsql
import json

TURSO_URL = "https://animenest-animenest.aws-ap-south-1.turso.io" 
TURSO_AUTH_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicm8iLCJpYXQiOjE3OTUzNTc2NDMsImlkIjoiMDFhMWJiNDQtM2MwMS03ZjRiLTlmYzQtY2RhODc4NTdjZGViIiwia2lkIjoic0RfVWxIcE1mMDk3d25UemNHdHJTd3R6RjdseXFLbU1pekhTMDZFQkNtWSIsInJpZCI6ImE0ZTFiNzYyLTliMTYtNDY3YS05OTQwLWZjMWJjNmE0NDJkNSJ9.f8MuCi1bvJQm3p1ufiRpXsjTgkHcmZfy5_XBVfv3KLTV0isu5M1YSyaDDKwSLnYljca4FGF68ZSE-jMPl_RkBg"

conn = libsql.connect(TURSO_URL, auth_token=TURSO_AUTH_TOKEN)

# सिर्फ 1 रो (Row) मंगा रहे हैं चेक करने के लिए
cursor = conn.execute("SELECT * FROM animenest_db LIMIT 1")
columns = [desc[0] for desc in cursor.description]
row = cursor.fetchone()

print("👇 डेटाबेस के कॉलम्स (Keys):")
print(columns)

if row:
    print("\n👇 पहली रो का डेटा:")
    data_dict = dict(zip(columns, row))
    for key, value in data_dict.items():
        # अगर डेटा बहुत लंबा है तो उसे छोटा करके दिखाएंगे
        str_val = str(value)
        if len(str_val) > 100:
            str_val = str_val[:100] + "..."
        print(f"➡️ {key} : {str_val}")
        
conn.close()