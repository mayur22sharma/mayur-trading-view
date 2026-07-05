import streamlit as st
import os
os.environ["OPENBB_BUILD_ON_IMPORT"] = "False"  # This fixes the PermissionError

import pandas as pd
from openbb import obb  # Now this won't crash
import feedparser
import requests
from datetime import datetime
import re

st.set_page_config(layout="wide", page_title="Mayur AI Trading View", page_icon="📈")

# ========== REST OF YOUR CODE STAYS THE SAME ==========
X_HANDLE = "mayur22sharma"
TWILIO_SID = st.secrets.get("TWILIO_SID", "")
TWILIO_TOKEN = st.secrets.get("TWILIO_TOKEN", "")
TWILIO_WHATSAPP_FROM = st.secrets.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
WHATSAPP_TO = st.secrets.get("WHATSAPP_TO", "")

# ... keep all other functions exactly as I posted before ...
