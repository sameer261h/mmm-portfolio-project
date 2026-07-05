"""One-time helper: turn your downloaded OAuth Desktop client JSON into a
Google Ads API refresh token.

What this does:
1. Reads the client_id/client_secret out of the JSON file you downloaded from
   Google Cloud Console (Auth Platform -> Clients -> your Desktop client).
2. Opens your default browser to Google's consent screen. Log in as the
   Google account that owns your Ads manager account (MCC) and click Allow.
3. Prints a refresh token to the terminal. Copy that into your .env file as
   GOOGLE_ADS_REFRESH_TOKEN=<the token>.

You only need to run this once. The refresh token does not expire on its own
(it lasts until you revoke it or leave the app in "Testing" mode too long
without use), so the app can use it to get new short-lived access tokens
without you logging in again.

Usage:
    conda activate mmm
    python scripts/generate_refresh_token.py /path/to/your-downloaded-client.json
"""

from __future__ import annotations

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

# This is the one scope the Google Ads API needs. Don't add others.
SCOPES = ["https://www.googleapis.com/auth/adwords"]


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/generate_refresh_token.py /path/to/client.json")
        sys.exit(1)

    client_secrets_path = sys.argv[1]

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, scopes=SCOPES)

    # Opens your browser, spins up a temporary local server to catch the
    # redirect after you click "Allow". Close the browser tab once it says
    # you can return to the terminal.
    credentials = flow.run_local_server(port=0)

    print("\nSuccess! Add this line to your .env file:\n")
    print(f"GOOGLE_ADS_REFRESH_TOKEN={credentials.refresh_token}")
    print()


if __name__ == "__main__":
    main()
