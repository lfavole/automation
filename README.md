# Automation

Automatically create Todoist tasks when I receive a new email.

## Requirements

- Python >= 3.12

## How to use

(:bulb: Tip: middle-click to open links in a new tab)

1. Create a `.env` file and open it.

2. Add these two lines:
   ```
   GMX_USER=(your GMX email address)
   GMX_PASSWORD=(your GMX password)
   ```
   You will need to create an app-specific password if you have 2FA enabled.

3. Get your Google credentials: (You can close the tabs at the end of each step)

   - Go to https://console.cloud.google.com/projectcreate and click on *Create*.

     Put whatever you want for the *Project name*.

   - Go to https://console.cloud.google.com/auth/overview/create and fill in the form (if there is no form, you can close the tab).

     Set the *Audience* to *External* and, finally, click on *Create*.

   - Go to https://console.cloud.google.com/apis/library/gmail.googleapis.com and click on *Enable*

   - Go to https://console.cloud.google.com/auth/audience.

     At the bottom, in the *Test users* section, click on *Add users*, add your email address and save.

   - Go to https://console.cloud.google.com/auth/clients

   - Click on *Create a client* and select *Web app*.

     Add `http://127.0.0.1:5000/google` as a *Redirect URI* and click on *Create*.

   - Click on the *Web client* you just created.

   - Open the `.env` file and add these two lines:
     ```
     GOOGLE_CLIENT_ID=(the Client ID that you see on the webpage, looks like ... .apps.googleusercontent.com)
     GOOGLE_CLIENT_SECRET=(the Client secret that you see on the webpage, looks like GOCSPX-...)
     ```

4. Get your Todoist credentials:

   - Go to https://developer.todoist.com/appconsole.html and click on *Create a new app*

     Put whatever you want for the *App name* and *App service URL* (the latter is optional).

   - Set the *OAuth redirect URL* to `http://127.0.0.1:5000/todoist` and click on *Save settings*.

   - Open the `.env` file and add these two lines:
     ```
     TODOIST_CLIENT_ID=(the Client ID that you see on the webpage, looks like 0123456789abcdef0123456789abcdef)
     TODOIST_CLIENT_SECRET=(the Client secret that you see on the webpage, looks like 0123456789abcdef0123456789abcdef)
     ```

5. ```
   pip install flask
   ```

6. ```
   python get_token_app.py
   ```

7. Go to http://127.0.0.1:5000/google and authorize your Google account.

   If there is a warning message that says *Google hasn't verified this app*, click on *Continue*.

8. Go to http://127.0.0.1:5000/todoist and authorize your Todoist account.

9. Go to the GitHub repo, click on the *Settings* tab and then click on *Secrets and variables* and on *Actions*.

   For each line in the `.env` file (for example `GMX_PASSWORD=abcdef`), click on *New repository secret*, write `GMX_PASSWORD` in the *Name* field and `abcdef` in the *Secret* field.

10. Click on the *Actions* tab and click on *Automation* in the left pane.

    Then click on *Run workflow* in the blue ribbon and confirm by clicking the green *Run workflow* button.

    There should be a new line on the page, click on it.

    After a few seconds, there will be either :white_check_mark: or :x: at the left.
    - If there is :white_check_mark:, everything works! :partying_face:
    - If there is :x:, click on *:x: `automation* in the left pane, read the logs, read again this page and retry.
