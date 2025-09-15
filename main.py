import os
import psycopg2
import csv
import io
import base64
import time
import ssl
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

# Load environment variables
load_dotenv()

# --- Database Config ---
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT")

# --- SendGrid Config ---
SENDGRID_API_KEY = os.getenv("KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")
TO_EMAILS = os.getenv("TO_EMAILS").split(",")  # multiple recipients

# --- Disable SSL verification (SendGrid SSL patch) ---
ssl._create_default_https_context = ssl._create_unverified_context


def send_email(message, retries=3, delay=5):
    """Send email with retries"""
    for attempt in range(1, retries + 1):
        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)
            print(f"✅ Email sent! Status Code: {response.status_code}")
            return True
        except Exception as e:
            print(f"❌ Attempt {attempt} failed: {e}")
            if attempt < retries:
                print(f"⏳ Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("❌ All attempts failed. Email not sent.")
                return False


def main_email_job():
    """Main function that generates feedback report emails"""
    try:
        # --- Connect to PostgreSQL ---
        conn = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()
        print("✅ Connected to database!")

        # Get ALL feedback forms
        cur.execute("""
            SELECT f.feedback_id, f.title, c.course_name, 
                   m.first_name || ' ' || m.last_name AS mentor_name, 
                   f.course_id
            FROM feedback_forms f
            JOIN courses c ON f.course_id = c.course_id
            JOIN mentors m ON f.mentor_id = m.mentor_id;
        """)
        feedback_forms = cur.fetchall()

        # --- CASE: No feedback forms found ---
        if not feedback_forms:
            print("⚠️ No feedback forms found in the database.")

            message = Mail(
                from_email=FROM_EMAIL,
                to_emails=TO_EMAILS,
                subject="📢 Feedback Reports - No Feedbacks Found",
                html_content="""
                <html>
                <body style="font-family: Arial, sans-serif; color: #333; background: #f9f9f9;">
                    <!-- Header Logo -->
                    <div style="text-align: center; padding: 15px; background: #2c3e50;">
                        <img src="https://i.ibb.co/mNqJ5hc/solvv-logo.png" alt="Solvv Logo" style="height:60px;">
                    </div>
                    <h2 style="color:#e74c3c;">⚠️ No Feedback Forms Found</h2>
                    <p>There are currently <b>no feedback forms</b> available.</p>
                    <p>This is an automated notification from <b>Solvv Platform</b>.</p>
                    <!-- Footer -->
                    <div style="margin-top: 30px; padding: 10px; background: #2c3e50; color: white; text-align: center; font-size: 12px;">
                        © 2025 Solvv Platform · Automated Email System
                    </div>
                </body>
                </html>
                """
            )
            send_email(message)
            cur.close()
            conn.close()
            return

        # --- CASE: Feedback forms exist ---
        attachments = []
        summary_html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; color: #333; background: #f9f9f9; }
                h2 { color: #2c3e50; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #2c3e50; color: white; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                .pending { color: #e74c3c; font-weight: bold; }
                .completed { color: #27ae60; font-weight: bold; }
            </style>
        </head>
        <body>
            <div style="text-align: center; padding: 15px; background: #2c3e50;">
                <img src="https://i.ibb.co/mNqJ5hc/solvv-logo.png" alt="Solvv Logo" style="height:60px;">
            </div>

            <h2>📊 Feedback Reports Summary</h2>
            <table>
                <tr>
                    <th>Feedback Title</th>
                    <th>Course</th>
                    <th>Mentor</th>
                    <th>Responses</th>
                    <th>Pending Students</th>
                </tr>
        """

        for feedback_id, title, course_name, mentor_name, course_id in feedback_forms:
            # Count responses vs total participants
            cur.execute("SELECT COUNT(*) FROM enrollments WHERE course_id = %s;", (course_id,))
            total_participants = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM feedback_responses WHERE feedback_id = %s;", (feedback_id,))
            responses_received = cur.fetchone()[0]

            # Export responses to CSV
            cur.execute("""
                SELECT u.first_name, u.last_name, u.email, 
                       r.response_text, r.rating, r.submitted_at
                FROM feedback_responses r
                JOIN users u ON r.user_id = u.user_id
                WHERE r.feedback_id = %s;
            """, (feedback_id,))
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]

            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(cols)
            writer.writerows(rows)
            encoded_file = base64.b64encode(csv_buffer.getvalue().encode()).decode()

            safe_course_name = course_name.replace(" ", "_")
            attachments.append(
                Attachment(
                    FileContent(encoded_file),
                    FileName(f"{safe_course_name}.csv"),
                    FileType("text/csv"),
                    Disposition("attachment")
                )
            )

            # Pending students
            cur.execute("""
                SELECT u.first_name, u.last_name
                FROM enrollments e
                JOIN users u ON e.user_id = u.user_id
                WHERE e.course_id = %s
                AND u.user_id NOT IN (
                    SELECT user_id FROM feedback_responses WHERE feedback_id = %s
                );
            """, (course_id, feedback_id))
            pending_students = cur.fetchall()

            pending_list = ", ".join([f"{fn} {ln}" for fn, ln in pending_students]) \
                if pending_students else "<span class='completed'>None 🎉</span>"

            summary_html += f"""
                <tr>
                    <td>{title}</td>
                    <td>{course_name}</td>
                    <td>{mentor_name}</td>
                    <td>{responses_received} / {total_participants}</td>
                    <td class='pending'>{pending_list}</td>
                </tr>
            """

        summary_html += """
            </table>
            <p>📎 Attached are the detailed CSV reports for each feedback form.</p>
            <div style="margin-top: 30px; padding: 10px; background: #2c3e50; color: white; text-align: center; font-size: 12px;">
                © 2025 Solvv Platform · Automated Email System
            </div>
        </body>
        </html>
        """

        # Prepare ONE Email
        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=TO_EMAILS,
            subject="📢 All Feedback Reports",
            html_content=summary_html
        )

        for att in attachments:
            message.add_attachment(att)

        send_email(message)
        cur.close()
        conn.close()

    except Exception as e:
        print("❌ Error:", str(e))


if __name__ == "__main__":
    main_email_job()
