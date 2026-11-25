# Playwright की आधिकारिक इमेज जिसमें सारे डिपेंडेंसीज़ पहले से हैं
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# 🛡️ SECURITY FIX: Ghostscript Vulnerability (CVE-2026-125396) को पैच करने के लिए
# यह कमांड सिस्टम को अपडेट करके Ghostscript का सुरक्षित वर्ज़न इंस्टॉल करेगा।
RUN apt-get update && \
    apt-get install -y --no-install-recommends ghostscript && \
    rm -rf /var/lib/apt/lists/*

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
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "120", "--workers", "1", "app:app"]