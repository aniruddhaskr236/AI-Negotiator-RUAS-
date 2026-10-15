import os
import pytest

# Configure fast timeouts for unit tests so test suite runs in seconds
os.environ["CALL_ANSWER_TIMEOUT"] = "0.1"
os.environ["DEMO_CONTROLS_ENABLED"] = "1"

# Re-initialize settings with new test environment variables
from backend import config
config.settings = config.Settings()
