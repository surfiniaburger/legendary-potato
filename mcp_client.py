# Make sure to have 'gradio_client' in your requirements.txt
from gradio_client import Client
import time

def query_zk_jbfuzz_from_client(user_query: str):
    """
    Connects to the ZK-JBFuzz Hugging Face Space, sends a query,
    and gets back a generated answer. Includes a retry mechanism for cold starts.
    """
    # --- Configuration for the retry mechanism ---
    MAX_RETRIES = 3
    # Delay between retries in seconds. Hugging Face spaces can take time to wake up.
    RETRY_DELAY_SECONDS = 60

    print("Connecting to Hugging Face Space: surfiniaburger/ZK-JBFuzz...")
    time.sleep(5)  # Wait for a few seconds before connecting
    try:
        # 1. Connect to your public Hugging Face Space
        client = Client("https://surfiniaburger-zk-jbfuzz.hf.space/")
        print("Connection successful.")
    except Exception as e:
        print(f"Fatal: Could not connect to the Gradio client. {e}")
        return None

    # 2. Loop for retry attempts
    for attempt in range(MAX_RETRIES):
        try:
            print(f"--- Attempt {attempt + 1} of {MAX_RETRIES} ---")
            print(f"Sending query: '{user_query}'...")
            
            # 3. Call the specific function on the server.
            # The input component in your app.py is named 'query_input'.
            # The 'fn_index' is 0 because it's the first (and only) function
            # attached to an event in your Gradio app.
            result = client.predict(
                user_query,
                fn_index=0
            )

            print("✅ Answer received successfully!")
            print("--- Generated Answer ---")
            print(result)
            print("------------------------")
            return result  # If successful, return the result and exit the function

        except Exception as e:
            print(f"Attempt {attempt + 1} failed. Error: {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"Server may be experiencing a cold start. Retrying in {RETRY_DELAY_SECONDS} seconds...")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print("All retry attempts have failed. The server might be unavailable or has an error.")
                return None # All retries failed, exit the function

# --- Example Usage ---
if __name__ == '__main__':
    # This is the query you want to send to your Gradio application.
    example_query = "What are the latest experimental treatments for H3K27M-mutant DIPG?"
    
    query_zk_jbfuzz_from_client(example_query)