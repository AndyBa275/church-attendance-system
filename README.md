# 🏛️ Church Attendance System

A cloud-based attendance and management system for churches using Streamlit and Google Sheets.

## 📱 Features
- ✅ Attendance tracking by Home Cell Groups
- 💰 Offerings and tithes management
- 🔍 Member search and directory
- 📢 Announcements system
- ⚙️ Admin panel for user management
- 📊 Reports and analytics

## 🚀 Deployment Instructions

### Step 1: Create GitHub Repository
1. Go to https://github.com/new
2. Repository name: `church-attendance-system`
3. Make it **Private** (to protect church data)
4. Click "Create repository"

### Step 2: Upload Files
Upload these files to your repository:
- `church_app.py` (main application)
- `requirements.txt` (dependencies)
- `README.md` (this file)

**DO NOT upload `credentials.json` or `secrets.toml`** - these contain sensitive data!

### Step 3: Deploy to Streamlit Cloud
1. Go to https://share.streamlit.io/
2. Sign in with your GitHub account
3. Click "New app"
4. Select your repository: `church-attendance-system`
5. Main file: `church_app.py`
6. Click "Advanced settings"
7. In the "Secrets" section, paste the entire contents of your `secrets.toml` file
8. Click "Deploy"

### Step 4: Share with Your Church
After deployment (2-3 minutes), you'll get a URL like:
```
https://church-attendance-system-yourname.streamlit.app
```

Share this URL with church members to access from their phones!

## 👥 Default Login Credentials

**Admin Account:**
- Username: `admin`
- Password: `admin123`

**Accountant Account:**
- Username: `accountant`
- Password: `account123`

⚠️ **Change these passwords after first login!**

## 📊 Google Sheets Setup

The app connects to Google Sheets with these tabs:
- **Members Master** - Church member directory
- **Church Attendance** - Attendance records
- **Church Offerings** - Financial records
- **Church Users** - System users
- **Church Announcements** - Church announcements

## 🔒 Security Notes

1. Keep your `secrets.toml` and `credentials.json` files secure
2. Never commit them to GitHub
3. Change default passwords immediately
4. Make your GitHub repository Private
5. Only share the app URL with authorized users

## 📱 Mobile Access

This app is fully mobile-responsive! Church members can:
- Save the URL to their phone's home screen
- Mark attendance from anywhere
- View announcements and member directory
- Access from any web browser

## 🆘 Support

If you encounter issues:
1. Check that your Google Sheet is shared with the service account email
2. Verify all sheet tab names match exactly
3. Ensure the service account has "Editor" permissions
4. Check Streamlit Cloud logs for error messages

## 📝 License

This is a private church management system. Not for public distribution.