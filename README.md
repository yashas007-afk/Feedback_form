# 📩 Feedback Form Automation (PostgreSQL + SendGrid)

This project automates **course feedback collection** and sends **thank-you emails** to participants after completing a course.  
It integrates:

- 🐘 **PostgreSQL** → Stores courses, participants, questions, and feedback responses  
- ✉️ **SendGrid** → Sends automated thank-you emails with additional resources  
- 🐍 **Python (FastAPI/Script)** → Handles database interaction and email sending  
- 🔑 **.env Configuration** → Keeps API keys and credentials safe  

---

## 🚀 Features

✅ Store and manage feedback for multiple courses  
✅ Automatically trigger a thank-you email when feedback is submitted  
✅ Retry mechanism for failed email deliveries  
✅ Uses `.env` file for secure credentials management  


Create a virtual environment
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows

Install dependencies

4️⃣ Configure .env

Create a file named .env in the root directory:

DB_HOST=localhost
DB_PORT=5432
DB_NAME=thankdb
DB_USER=postgres
DB_PASS=yourpassword

SENDGRID_API_KEY=SG.xxxxxxx
FROM_EMAIL=your-email@example.com
TO_EMAILS=recipient1@example.com,recipient2@example.com


⚠️ Never commit .env to GitHub. It’s already in .gitignore.
