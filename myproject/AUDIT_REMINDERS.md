# Monthly Data Audit Reminder System

This system provides automated reminders for monthly data audits and sanitization during the last 7 days of each month.

## 🎯 Features

- **Automated Detection**: Automatically detects when you're in the last 7 days of any month
- **Visual Banner**: Shows a prominent warning banner on the home page with audit checklist
- **Management Command**: Provides Django management command for manual checks
- **Cron Integration**: Easy setup with automated cron job scheduling

## 📋 What Gets Reminded

The system reminds you to:
- ✅ Review order data accuracy
- ✅ Clean up duplicate entries  
- ✅ Verify MRN and billing completeness
- ✅ Update dealer and vehicle information

## 🚀 Quick Setup

### Option 1: Automated Setup (Recommended)
```bash
cd myproject/
python3 setup_audit_cron.py
```

### Option 2: Manual Setup
1. Set up the cron job manually:
```bash
crontab -e
# Add this line:
0 9 * * * cd /path/to/myproject && python3 manage.py check_audit_reminder
```

## 🔧 Usage

### Manual Check
Test if audit reminder should be shown:
```bash
python3 manage.py check_audit_reminder
```

### View in Browser
- Navigate to the home page (`/`)
- During the last 7 days of any month, you'll see the audit reminder banner
- Click "View Analytics" to access data analysis tools
- Dismiss the banner by clicking the X button

## 📅 How It Works

1. **Daily Check**: System runs daily at 9:00 AM via cron job
2. **Date Calculation**: Determines if current date is within last 7 days of month
3. **Banner Display**: Shows reminder banner with countdown and checklist
4. **User Action**: Users can view analytics or dismiss the reminder

## 🎛️ Customization

### Change Reminder Period
Edit the `check_audit_reminder()` function in `orders/views.py`:
```python
if days_until_end <= 6:  # Change 6 to desired number of days - 1
```

### Modify Banner Content
Edit the banner HTML in `orders/templates/home.html`:
```html
{% if audit_reminder.show_reminder %}
<!-- Customize the banner content here -->
{% endif %}
```

### Adjust Cron Schedule
Modify the cron schedule in `setup_audit_cron.py`:
```python
# Current: Daily at 9:00 AM
cron_command = f"0 9 * * * cd {project_path} && python3 {manage_py} check_audit_reminder"

# Example: Twice daily at 9 AM and 5 PM
cron_command = f"0 9,17 * * * cd {project_path} && python3 {manage_py} check_audit_reminder"
```

## 🗓️ Example Scenarios

### January 2024
- Reminder starts: January 25 (7 days before month end)
- Banner shows: "7 days remaining in January 2024"
- Continues until: January 31

### February 2024 (Leap Year)
- Reminder starts: February 23 (7 days before month end)  
- Banner shows: "7 days remaining in February 2024"
- Continues until: February 29

### February 2025 (Regular Year)
- Reminder starts: February 22 (7 days before month end)
- Banner shows: "7 days remaining in February 2025"  
- Continues until: February 28

## 🔍 Troubleshooting

### Banner Not Showing
1. Check if you're in the last 7 days of the month
2. Verify the audit reminder function is working:
   ```bash
   python3 manage.py check_audit_reminder
   ```

### Cron Job Not Working
1. Check if cron service is running:
   ```bash
   sudo systemctl status cron
   ```
2. View cron logs:
   ```bash
   grep CRON /var/log/syslog
   ```
3. Verify crontab entry:
   ```bash
   crontab -l
   ```

### Permission Issues
Ensure the project directory and manage.py are executable:
```bash
chmod +x manage.py
```

## 📝 File Structure

```
myproject/
├── orders/
│   ├── management/
│   │   └── commands/
│   │       └── check_audit_reminder.py    # Management command
│   ├── templates/
│   │   └── home.html                      # Banner template
│   └── views.py                          # Reminder logic
├── setup_audit_cron.py                   # Automated setup
└── AUDIT_REMINDERS.md                    # This documentation
```

## 🎯 Benefits

- **Proactive**: Never forget monthly audits again
- **User-Friendly**: Clear visual reminders with actionable checklists  
- **Flexible**: Easy to customize timing and content
- **Automated**: Set up once, works every month
- **Integrated**: Seamlessly fits into existing workflow

## 🔄 Maintenance

The system requires no ongoing maintenance once set up. The cron job will continue running monthly, and the reminder logic automatically adapts to different month lengths (28, 29, 30, or 31 days).