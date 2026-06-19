import os
import sys

# Ensure the script directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import applier

def main():
    print("Executing scheduled AI Job Applier daemon...")
    try:
        applied = applier.run_auto_apply_queue()
        print(f"Scheduled run completed. Applied to {applied} jobs.")
    except Exception as e:
        print(f"Error during scheduled run: {e}")

if __name__ == "__main__":
    main()
