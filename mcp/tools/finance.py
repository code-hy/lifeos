from mcp.server import mcp_tool
import logging

logger = logging.getLogger("LifeOS.Tools.Finance")

# Mock financial database
mock_accounts = {
    "Checking": 2500.50,
    "Savings": 12000.75,
    "Credit Card": -450.20
}

@mcp_tool()
def get_balance() -> dict:
    """
    Retrieve current balances across all accounts.
    """
    logger.info("Finance Tool: Querying account balances.")
    return mock_accounts

@mcp_tool()
def transfer_funds(amount: float, recipient: str, source_account: str = "Checking") -> str:
    """
    Transfer funds from a source account to a recipient.
    RESTRICTED: Requires manual user approval.
    """
    logger.info(f"Finance Tool: Initiating transfer of ${amount:.2f} to {recipient}.")
    if source_account not in mock_accounts:
        return f"Error: Source account '{source_account}' does not exist."
    
    if mock_accounts[source_account] < amount:
        return f"Error: Insufficient funds in '{source_account}' (Balance: ${mock_accounts[source_account]:.2f})."
    
    mock_accounts[source_account] -= amount
    return f"Transferred ${amount:.2f} to {recipient} from {source_account}."
