from openai import OpenAI
import time

class OpenAIClient():
    def __init__(self):
        # openai.api_key = os.environ["OPENAI_API_KEY"]
        # openai.api_base = os.environ["OPENAI_API_BASE"]
        self.client = OpenAI(
            base_url="",
            api_key=""
        )
    
    def getResponse(self, **kwargs):
        for _ in range(5):
            try:
                print(f"new message call. try...")
                response = self.client.chat.completions.create(**kwargs, timeout=60)
                time.sleep(0.2)
                return response
            except Exception as e:
                if "service unavailable" in str(e).lower() or "503" in str(e):
                    print("service unavailable error")
                    time.sleep(1)
                else:
                    print(f"Error occurred: {e}.\n")
                    time.sleep(1)
        raise Exception("Failed to get response in 5 attempts.")