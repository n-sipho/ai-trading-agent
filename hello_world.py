from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.capabilities import Thinking, WebSearch
# import os

# 1. Load variables from the .env file into the system environment
load_dotenv()

gemma_studio_model = GoogleModel(
    model_name="gemma-4-31b-it",  # Target the flagship open model
)

agent = Agent(
    gemma_studio_model,
    instructions="Be concise, reply with one sentence.",
    capabilities=[Thinking(), WebSearch(local='duckduckgo')],
)

result = agent.run_sync('What was the mass of the largest meteorite found this year?')
print(result.output)
"""
The largest meteorite recovered this year weighed approximately 7.6 kg, found in the Sahara Desert in January.
"""