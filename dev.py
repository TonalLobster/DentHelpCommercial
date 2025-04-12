"""
Development helper script for running the application locally.
This script provides convenience commands for typical development tasks.

Usage:
    python dev.py [command]

Commands:
    run          - Run the development server
    init_db      - Initialize the database
    migrate      - Generate database migrations
    upgrade      - Apply database migrations
    seed         - Seed the database with sample data
    test         - Run the test suite
    clean        - Remove __pycache__ files and directories
    reset_db     - Reset the database (drops all tables and recreates them)
    shell        - Run a Python shell in the Flask app context
    worker       - Run a Celery worker for background tasks
    beat         - Run Celery beat for scheduled tasks
    flower       - Run Flower (Celery monitoring tool)
"""

import os
import sys
import subprocess
import shutil

def run_flask_command(command):
    """Run a Flask CLI command."""
    os.environ["FLASK_APP"] = "wsgi.py"
    full_command = f"flask {command}"
    return subprocess.call(full_command, shell=True)

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1]
    
    if command == "run":
        os.environ["FLASK_APP"] = "wsgi.py"
        os.environ["FLASK_ENV"] = "development"
        os.environ["FLASK_DEBUG"] = "1"
        run_flask_command("run --reload")
    
    elif command == "init_db":
        run_flask_command("db init")
    
    elif command == "migrate":
        message = ""
        if len(sys.argv) > 2:
            message = f' -m "{sys.argv[2]}"'
        run_flask_command(f"db migrate{message}")
    
    elif command == "upgrade":
        run_flask_command("db upgrade")
    
    elif command == "seed":
        run_flask_command("--app seed.py seed-db")
    
    elif command == "test":
        subprocess.call("pytest", shell=True)
    
    elif command == "clean":
        # Remove __pycache__ directories and .pyc files
        for root, dirs, files in os.walk("."):
            for dir_name in dirs:
                if dir_name == "__pycache__":
                    cache_dir = os.path.join(root, dir_name)
                    print(f"Removing {cache_dir}")
                    shutil.rmtree(cache_dir)
            
            for file_name in files:
                if file_name.endswith(".pyc"):
                    pyc_file = os.path.join(root, file_name)
                    print(f"Removing {pyc_file}")
                    os.remove(pyc_file)
    
    elif command == "reset_db":
        confirm = input("Are you sure you want to reset the database? This will delete all data. (y/n): ")
        if confirm.lower() == "y":
            run_flask_command("db downgrade base")
            run_flask_command("db upgrade")
            print("Database reset complete.")
        else:
            print("Database reset cancelled.")
    
    elif command == "shell":
        run_flask_command("shell")
    
    elif command == "worker":
        # Run a Celery worker for processing background tasks
        subprocess.call("celery -A app.celery_worker.celery worker --loglevel=info", shell=True)
    
    elif command == "beat":
        # Run Celery beat for scheduled tasks
        subprocess.call("celery -A app.celery_worker.celery beat --loglevel=info", shell=True)
    
    elif command == "flower":
        # Run Flower for Celery monitoring
        subprocess.call("celery -A app.celery_worker.celery flower --port=5555", shell=True)
    
    else:
        print(f"Unknown command: {command}")
        print(__doc__)

if __name__ == "__main__":
    main()