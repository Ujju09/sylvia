#!/usr/bin/env python3
"""
Setup script for monthly data audit reminders using cron.

This script helps you set up a cron job that will run every day during
the last 7 days of each month to remind about data audits.

Usage:
    python3 setup_audit_cron.py
"""

import sys
import subprocess
from pathlib import Path


def get_project_path():
    """Get the absolute path to the Django project"""
    return Path(__file__).parent.absolute()


def create_cron_entry():
    """Create a cron entry for daily audit reminder checks"""
    project_path = get_project_path()
    manage_py = project_path / "manage.py"
    
    # Cron entry to run daily at 9:00 AM
    cron_command = f"0 9 * * * cd {project_path} && python3 {manage_py} check_audit_reminder"
    
    return cron_command


def setup_cron():
    """Set up the cron job for audit reminders"""
    try:
        # Get current crontab
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        current_crontab = result.stdout if result.returncode == 0 else ""
        
        # Create new cron entry
        cron_entry = create_cron_entry()
        
        # Check if our cron job already exists
        if 'check_audit_reminder' in current_crontab:
            print("✅ Audit reminder cron job already exists!")
            print(f"Current entry: {cron_entry}")
            return True
        
        # Add our cron job
        new_crontab = current_crontab.rstrip() + '\n' + cron_entry + '\n'
        
        # Write new crontab
        process = subprocess.run(['crontab', '-'], input=new_crontab, text=True)
        
        if process.returncode == 0:
            print("✅ Successfully added audit reminder cron job!")
            print(f"Cron entry: {cron_entry}")
            print("\n📋 The system will now check daily at 9:00 AM if audit reminders should be shown.")
            print("💡 You can also manually run: python3 manage.py check_audit_reminder")
            return True
        else:
            print("❌ Failed to add cron job")
            return False
            
    except FileNotFoundError:
        print("❌ crontab command not found. Please install cron or set up the job manually.")
        print(f"Manual cron entry: {create_cron_entry()}")
        return False
    except Exception as e:
        print(f"❌ Error setting up cron job: {e}")
        return False


def main():
    """Main function"""
    print("🔧 Setting up Monthly Data Audit Reminder System")
    print("=" * 50)
    
    project_path = get_project_path()
    print(f"📁 Project path: {project_path}")
    
    # Check if manage.py exists
    manage_py = project_path / "manage.py"
    if not manage_py.exists():
        print(f"❌ manage.py not found at {manage_py}")
        sys.exit(1)
    
    print("\n🕘 Setting up cron job...")
    if setup_cron():
        print("\n✅ Setup completed successfully!")
        print("\n📋 How it works:")
        print("• The system checks daily if we're in the last 7 days of the month")
        print("• If yes, a banner appears on the home page with audit reminders")
        print("• The banner includes a checklist of audit tasks to complete")
        print("• Users can dismiss the banner or click to view analytics")
        
        print("\n🔧 Management commands:")
        print(f"• Manual check: cd {project_path} && python3 manage.py check_audit_reminder")
        print("• View current crontab: crontab -l")
        print("• Edit crontab: crontab -e")
        
    else:
        print("\n❌ Setup failed. You may need to set up the cron job manually.")
        print(f"\nManual setup instructions:")
        print(f"1. Run: crontab -e")
        print(f"2. Add this line: {create_cron_entry()}")
        print(f"3. Save and exit")


if __name__ == "__main__":
    main()