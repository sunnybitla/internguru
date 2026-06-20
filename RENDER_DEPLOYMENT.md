# Hosting on Render: Step-by-Step Guide

This guide explains how to deploy and host the **AI Job Applier Agent** on **Render**.

---

## ⚠️ Important Considerations before Deploying

1. **Free Tier Spin-down**: On Render's Free tier, services automatically spin down (sleep) after **15 minutes of inactivity**. When a request comes in, it will take about 50 seconds to spin back up.
2. **Scheduled Tasks**: If the server is spun down, the internal Python background scheduler will not trigger at the scheduled Monday time. 
   - *Solution*: Use an external free cron service (like [Cron-Job.org](https://cron-job.org)) to ping `/api/trigger-run` once a week, or ping `/api/profile` every 10 minutes to keep the server awake.
3. **SQLite Persistence**: On the Free Tier, Render's disk is ephemeral. Any data saved (like your `data.db` database and uploaded `resume.pdf`) will be lost whenever the server restarts or redeploys.
   - *Solution (Free)*: You will need to configure your profile and upload your resume again if the server restarts.
   - *Solution (Paid - Recommended)*: Upgrade your Render Web Service to the **Starter tier** (~$7/month) and attach a **Persistent Disk** (~$1/month) mounted at `/data`. We have already configured the app to support this via the `DATA_DIR` environment variable!

---

## Step 1: Push Your Code to GitHub

Render deploys directly from a GitHub repository.

1. Create a **Private** repository on [GitHub](https://github.com).
2. Initialize Git in this directory (if not already done) and commit all files:
   ```bash
   git init
   git add .
   git commit -m "Configure app for Render deployment"
   ```
3. Push your repository to GitHub:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git branch -M main
   git push -u origin main
   ```

---

## Step 2: Deploy on Render

### Option A: Using the Render Blueprint (Recommended & Fastest)

We have created a `render.yaml` file in the root of the project. Render can read this file and set everything up automatically:

1. Log in to [Render](https://dashboard.render.com/).
2. Click **New +** in the top right and select **Blueprint**.
3. Connect your GitHub repository.
4. Render will read `render.yaml` and prompt you to approve the configuration.
5. Click **Apply**. Render will automatically build the Docker image and deploy the web service!

---

### Option B: Manual Configuration

If you prefer to configure the Web Service manually:

1. Log in to [Render](https://dashboard.render.com/).
2. Click **New +** and select **Web Service**.
3. Connect your GitHub repository.
4. Configure the following settings:
   - **Name**: `ai-job-applier-agent`
   - **Language**: `Docker` (Render will automatically detect the `Dockerfile` we created)
   - **Branch**: `main`
   - **Region**: Select the region closest to you.
   - **Instance Type**: Select **Free** (or Starter if you want persistence).
5. Open the **Advanced** section and add the following **Environment Variables**:
   - `PORT`: `10000`
   - `DATA_DIR`: `/data` (if using persistent disk, otherwise leave it default or point it to a writeable path like `/tmp`)
6. *(Optional)* If using a paid tier, scroll down to **Disks**:
   - Click **Add Disk**.
   - **Name**: `sqlite-data`
   - **Mount Path**: `/data`
   - **Size**: `1 GiB`
7. Click **Create Web Service**.

---

## Step 3: Configure External Cron to Run Auto-Apply

Because the app runs on the cloud, the Windows Task Scheduler toggle in the UI is disabled. The app relies on the internal Python scheduler or a simple HTTP request to start applying.

To automate applying every week for free (even on the Free tier):

1. Go to [Cron-Job.org](https://cron-job.org) and create a free account.
2. Click **Create Cronjob**.
3. Configure the following:
   - **Title**: `AI Job Applier Auto-Run`
   - **URL**: `https://your-render-app-url.onrender.com/api/trigger-run`
   - **Request Method**: `POST`
   - **Schedule**: Set it to run every Monday at your preferred time (e.g., `09:00` or via user cron expression `0 9 * * 1`).
4. Click **Create**.

This will send a POST request to your app once a week, wake it up if it's sleeping, and automatically trigger the auto-apply queue for all jobs you have added!
