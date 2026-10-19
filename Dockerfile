# Playwright की ऑफिशियल इमेज जिसमें सारे डिपेंडेंसीज़ पहले से हैं
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Python को अनबफर्ड मोड में चलाओ
ENV PYTHONUNBUFFERED=1

# काम करने की डायरेक्टरी सेट करो
WORKDIR /app

# पहले requirements.txt कॉपी करो और इंस्टॉल करो
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# बाकी सारा कोड कॉपी करो
COPY . /app/

# Render के लिए Gunicorn कमांड
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "120", "--workers", "1", "app:create_app()"]