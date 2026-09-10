# Appwrite Setup Guide — TN StuScholar

Follow these steps once to connect your Appwrite backend. Takes ~5 minutes.

---

## Step 1 — Create an Appwrite account & project

1. Go to **https://cloud.appwrite.io** and sign up (free).
2. Click **Create Project**, give it any name (e.g. `tn-stuschoiar`).
3. Copy your **Project ID** from **Settings → Project ID**.

---

## Step 2 — Create a Database

1. In your project sidebar, click **Databases → Create Database**.
2. Name it anything (e.g. `scholarship_db`).
3. Copy the **Database ID** shown after creation.

---

## Step 3 — Create 3 Collections

Go to **Databases → your database → Create Collection** for each:

### Collection 1: `users`
| Attribute | Type | Size | Required |
|---|---|---|---|
| `name` | String | 100 | ✅ |
| `email` | String | 255 | ✅ |
| `password_hash` | String | 512 | ✅ |
| `created_at` | String | 50 | ❌ |

> Add an **Index**: Key=`email`, Type=**Unique**

---

### Collection 2: `tokens`
| Attribute | Type | Size | Required |
|---|---|---|---|
| `token` | String | 36 | ✅ |
| `email` | String | 255 | ✅ |
| `created_at` | String | 50 | ❌ |

---

### Collection 3: `applications`
| Attribute | Type | Size | Required |
|---|---|---|---|
| `email` | String | 255 | ✅ |
| `ref_id` | String | 50 | ✅ |
| `group_id` | String | 50 | ❌ |
| `scheme_id` | String | 100 | ✅ |
| `scheme_name` | String | 255 | ✅ |
| `benefit_value` | Integer | — | ✅ |
| `status` | String | 50 | ❌ |
| `applied_at` | String | 50 | ❌ |
| `guardian_name` | String | 255 | ❌ |
| `college_name` | String | 255 | ❌ |
| `account_number` | String | 100 | ❌ |
| `ifsc` | String | 20 | ❌ |

> Add an **Index**: Key=`email`, Type=**Key**

---

## Step 4 — Create an API Key

1. Go to **Settings → API Keys → Add API Key**.
2. Give it a name and enable the **Databases** scope (read + write).
3. Copy the generated key.

---

## Step 5 — Set up your `.env` file

In your project folder (`Studoscholars/`), copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Fill in your values:

```env
APPWRITE_ENDPOINT=https://cloud.appwrite.io/v1
APPWRITE_PROJECT_ID=<your Project ID>
APPWRITE_API_KEY=<your API Key>
APPWRITE_DATABASE_ID=<your Database ID>
APPWRITE_USERS_COLLECTION=users
APPWRITE_TOKENS_COLLECTION=tokens
APPWRITE_APPS_COLLECTION=applications
```

---

## Step 6 — Set Collection Permissions

For each collection, go to **Settings → Permissions** and add:

- Role: `Any` — **Read** + **Create** + **Update** + **Delete**

(For a production deployment, tighten these to authenticated users only.)

---

## Step 7 — Install dependencies & run

```powershell
pip install -r requirements.txt
python main.py
```

Open **http://127.0.0.1:8000** — all user registrations and applications now persist in Appwrite! ✅

---

## Step 8 — Deploy to Vercel

1. Push this project to a GitHub repository. Make sure `.env` is not committed.
2. In Vercel, click **Add New → Project** and import the repository.
3. Leave the framework preset and build command empty. Vercel uses `vercel.json` and `api/index.py`.
4. In **Project Settings → Environment Variables**, add these variables for **Production**, **Preview**, and **Development**:

```env
APPWRITE_ENDPOINT=https://cloud.appwrite.io/v1
APPWRITE_PROJECT_ID=<your Project ID>
APPWRITE_API_KEY=<your server API key>
APPWRITE_DATABASE_ID=<your Database ID>
APPWRITE_USERS_COLLECTION=users
APPWRITE_TOKENS_COLLECTION=tokens
APPWRITE_APPS_COLLECTION=applications
```

5. Deploy the project. Vercel will serve the frontend at `/` and the FastAPI endpoints at paths such as `/api`, `/login`, and `/match`.

If the API key previously stored in `.env.example` was real, revoke it in Appwrite and create a new server key before deploying.
