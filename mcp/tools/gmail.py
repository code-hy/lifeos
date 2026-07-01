from mcp.server import mcp_tool
import logging

logger = logging.getLogger("LifeOS.Tools.Gmail")

@mcp_tool()
def send_email(to: str, subject: str, body: str) -> str:
    """
    Send an email to a recipient.
    RESTRICTED: Requires manual user approval.
    """
    logger.info(f"Gmail Tool: Sending email to {to} | Subject: {subject}")
    return f"Email successfully sent to {to} under subject '{subject}'."

@mcp_tool()
def read_emails() -> list[dict]:
    """
    Read the latest unread emails from your inbox.
    """
    logger.info("Gmail Tool: Reading unread emails.")
    return [
        {
            "id": "email_1",
            "from": "wife@family.com",
            "subject": "Dinner tonight?",
            "body": "Hey! Are we still on for dinner at 7 PM? Let me know if your plans changed.",
            "received_at": "2026-07-01T00:30:00Z"
        },
        {
            "id": "email_2",
            "from": "billing@electricity-utility.com",
            "subject": "Your Monthly Electricity Bill - Alert",
            "body": "Your monthly utility bill is now ready. The total amount due is $452.12. This is 150% higher than your standard monthly average of $180.00.",
            "received_at": "2026-07-01T00:15:00Z"
        }
    ]
