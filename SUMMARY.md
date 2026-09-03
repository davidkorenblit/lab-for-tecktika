# 🚀 מסירת RAG Platform — סיכום יומי לצוות

**מה הוקם בפועל בענן, ומה כל אחד מקבל מוכן כדי להתחיל לכתוב קוד — בלי לחכות אחד לשני.**

---

### 📌 מסלול הפרויקט
* **`01 / infra`** — **הושלם** (תשתית Azure IaC פרוסה ומאומתת).
* **`02 / worker`** — **הושלם במלואו** (8/8 PR-ים קומטו ב-`feature/worker-pipeline`, כולל 100% טסטים).
* **`03 / backend`** — **טרם התחיל** (ה-Agent, הצ'אט וכלי הכתיבה — השרת חי, מחכה לקוד).
* **`04 / frontend`** — **טרם התחיל** (ממשק הצ'אט — כתובת חיה קיימת, מחכה ל-Build ראשון).

---

## 01 — מה נגמר בתשתית
* **Resource Group:** `rg-sharepoint-rag-dev` (`swedencentral`, פרט לפרונטאנד שיושב ב-`eastus2`). הכל ב-IaC (Bicep), פרוס בפועל ומאומת — לא רק כתוב.
* **Storage (Blob/Queue/Table), AI Search, Azure OpenAI (`gpt-4o` + `text-embedding-3-small`), Container App, Function App ו-Static Web App** — כולם קמו וזמינים.
* **הרשאות בין השירותים (RBAC)** דרך Managed Identity בלבד — אין מפתח או Connection String אחד בשום מקום.
* **כניסת משתמשים** דרך Entra ID מוגדרת ומאומתת.
* **דיפלוי אוטומטי מ-GitHub Actions** בכל push שנוגע ב-`infrastructure/`, מחובר ל-Azure בלי סוד שמור (OIDC).

---

## 📋 המשאבים המשותפים — מוכנים לשימוש
*כל הערכים כאן אינם סודות — הגישה בפועל היא תמיד דרך Managed Identity. אפשר להעתיק ישירות לקוד.*

| משאב | ערך |
| :--- | :--- |
| **Storage Account** | `stragpocdevqelri355piqlq` |
| **Blob Container** | `pdf-library` |
| **Queue** | `index-jobs` |
| **Poison Queue (DLQ)** | `index-jobs-poison` |
| **Table (סטטוס משימות)** | `jobstatus` |
| **AI Search Endpoint** | `https://srch-ragpoc-dev-qelri355piqlq.search.windows.net` |
| **Azure OpenAI Endpoint** | `https://aoai-ragpoc-dev-qelri355piqlq.openai.azure.com/` |
| **Chat Deployment** | `gpt-4o` (Standard, 10K TPM) |
| **Embedding Deployment** | `text-embedding-3-small` (GlobalStandard, 30K TPM, 1536d) |
| **Backend URL** | `ca-backend-ragpoc-dev-qelri355pi.redrock-32afe15c.swedencentral.azurecontainerapps.io` |
| **Frontend URL** | `delightful-river-0f09b360f.5.azurestaticapps.net` |
| **Entra Tenant ID** | `6fc8a795-8bcb-4e52-8b36-41c1971e6816` |
| **Entra Client ID** | `7267f8e7-50eb-4247-88b7-da2cc3adf6f6` |
| **API Scope** | `api://7267f8e7-50eb-4247-88b7-da2cc3adf6f6/access_as_user` |

---

## 02 — וורקר (Worker) — הושלם 100%!
**Azure Functions (Python v2, מחובר ל-`func-worker-ragpoc-dev-qelri355piqlq`)** — צורך הודעות מהתור, מעדכן סטטוס בטבלה, מפעיל אינדוקס, ומבצע מחיקה כירורגית.

### ✅ מה הושלם בפועל (בבראנץ' `feature/worker-pipeline`):
1. **שלד Python Functions v2 + מודלי Pydantic:**
   * `worker/config.py`: ריכוז הגדרות מרכזי ומשתני סביבה.
   * `worker/models/queue_message.py`: תבנית הודעת תור (`CREATE`, `UPDATE`, `DELETE`).
   * `worker/models/job_entity.py`: תבנית ישות סטטוס ב-Table Storage.
2. **Queue Trigger + פענוח מוגן (`worker/function_app.py`):**
   * האזנה לתור `index-jobs` + מפענח חסין המטפל בטקסט רגיל וגם ב-Base64.
3. **ניהול סטטוסים ב-Table Storage (`worker/services/job_service.py`):**
   * מכונת מצבים מלאה: `QUEUED` $\rightarrow$ `RUNNING` $\rightarrow$ `SUCCEEDED` / `FAILED`.
4. **בדיקת ETag מוגנת (`worker/services/blob_service.py`):**
   * בדיקת ETag בקריאה בודדת ל-Blob Storage. עיבוד חוזר על תוכן שלא השתנה הופך ל-no-op ומדלג מיד!
5. **נתב אירועים מרכזי (`worker/services/dispatcher.py`):**
   * נתב המפצל לוגיקה באופן חד לפי סוג האירוע (`CREATE`, `UPDATE`, `DELETE`).
6. **הפעלת אינדוקס ב-Azure AI Search (`worker/services/search_service.py`):**
   * הפעלה יזוקה של `client.run_indexer("pdf-chunks-indexer")`.
7. **מחיקה כירורגית (Surgical Deletion):**
   * שאילתת OData filter לפי `ParentDocumentID eq '{document_id}'` ומחיקה מלאה של ה-Chunks מהאינדקס ב-Bulk (מונע Ghost Chunks גם ב-`UPDATE`).
8. **טיפול בשגיאות ו-DLQ (`worker/host.json`):**
   * עדכון סטטוס `FAILED` יחד עם הודעת שגיאה בטבלה. מוגדר `maxDequeueCount: 5` להעברה אוטומטית לתור הרעיל (`index-jobs-poison`).
9. **סוויטת טסטים מלאה (`worker/tests/test_worker_pipeline.py`):**
   * **6/6 Unit Tests עברו ב-100% (ב-1.75 שניות)** ללא תלות בענן.

---

## 03 — בקאנד (Backend)
**FastAPI Agent (Container App חי — כרגע עם Image Placeholder בלבד)** — הצ'אט, הכלים, וניהול העבודות ברקע.

### 🔌 מוכן בשבילכם:
* Container App חי עם כתובת ציבורית, כל ה-Endpoints כבר מוגדרים כ-`env vars`.
* הרשאות RBAC מלאות דרך Managed Identity: `Blob/Queue/Table Contributor`, `Search Index Data Contributor`, `Cognitive Services OpenAI User`.
* `AZURE_TENANT_ID` ו-`AZURE_CLIENT_ID_API` כבר מוזרקים לאימות טוקנים נכנסים.

### ⏳ מה נשאר לבקאנד:
* Endpoint צ'אט עם streaming + היסטוריית שיחה.
* כלים מאומתים (Pydantic schema) להוספה/החלפה/מחיקה.
* אישור מפורש שנוקב בשם הקובץ לפני מחיקה/החלפה.
* הפעולות רצות כ-Job ברקע (זריקה לתור `index-jobs`), הצ'אט לא נחסם, והתוצאה שורדת רענון דף.
* אימות טוקן Entra ID נכנס מהפרונטאנד.

---

## 04 — פרונטאנד (Frontend)
**Static Web App (חי, ריק)** — ממשק הצ'אט שהמשתמש בפועל רואה.

### 🔌 מוכן בשבילכם:
* כתובת חיה: `delightful-river-0f09b360f.5.azurestaticapps.net`.
* Redirect URIs כבר רשומים ב-Entra ID גם ל-`localhost:5173` וגם לכתובת החיה — MSAL.js יעבוד בלי הגדרה נוספת.

### ⏳ מה נשאר לפרונטאנד:
* ממשק צ'אט עם streaming והיסטוריית שיחה.
* כניסה עם Entra ID (MSAL.js) מול ה-Tenant/Client ID בטבלה למעלה.
* מודאל אישור מפורש למחיקה/החלפה, נוקב בשם הקובץ.
* מעקב סטטוס Job ששורד רענון דף (polling מול הטבלה/בקאנד).

---

📚 **מסמכי רקע בריפו:** `ARCHITECTURE.md` (ארכיטקטורה) · `LIMITATIONS.md` (מגבלות) · `README.md` (הרצה).
