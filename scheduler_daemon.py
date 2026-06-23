import os
import sys

# Ensure the script directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import applier

def main():
    print("Executing scheduled AI Job Applier daemon...")
    user_id = 1
    if len(sys.argv) > 1:
        try:
            user_id = int(sys.argv[1])
        except ValueError:
            pass
    try:
        applied = applier.run_auto_apply_queue(user_id)
        print(f"Scheduled run completed for user {user_id}. Applied to {applied} jobs.")
    except Exception as e:
        print(f"Error during scheduled run: {e}")

if __name__ == "__main__":
    main()
