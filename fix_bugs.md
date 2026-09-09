# בדיקת מגילה מול main ומעקב תיקוני באגים — ספטמבר 2026

## תקלות שתוקנו מהדו"ח המקורי (6 תקלות)

| # | תקלה | סטטוס | ראיה בקוד |
|---|-------|--------|-----------|
| 1 | Worker לא רץ — `ModuleNotFoundError: pydantic` | ✅ תוקן | CI pipeline |
| 2 | דיפלוי תשתית מחק קוד Worker | ✅ תוקן | `infrastructure/` |
| 3 | אימות שבור (503) — סוד ריק דרס `AZURE_CLIENT_ID_API` | ✅ תוקן | CI pipeline |
| 4 | Worker נכשל ב-403 על `run_indexer()` | ✅ תוקן | Infra — Search Service Contributor |
| 5 | שאילתת RAG מול שדות לא קיימים (`chunkId` → `id`) | ✅ תוקן | [`config.py:27`](backend/app/core/config.py#L27) |
| 6 | היסטוריית שיחה 422 | ✅ תוקן | [`chat.py:277`](backend/app/api/v1/endpoints/chat.py#L277) |

## תקלה חוסמת — קידוד התור

| פריט | סטטוס | ראיה בקוד |
|-------|--------|-----------|
| `host.json` → `messageEncoding: "none"` | ✅ תוקן | [`host.json:18`](worker/host.json#L18) |
| `queue_service.py` שולח plain text | ✅ תואם | [`queue_service.py:17-18`](backend/app/services/queue_service.py#L17-L18) |
| `parse_queue_message` מטפל בשניהם | ✅ תואם | [`function_app.py:17-28`](worker/function_app.py#L17-L28) |

---

## שיפורים מהמגילה — מצב נוכחי

### 01 — הקובץ המצורף בלתי נראה למודל
* **סטטוס:** ✅ **תוקן**
* **ראיה בקוד:** [`runner.py:62-81`](backend/app/agent/runner.py#L62-L81) — הזרקת system message עם שם הקובץ בתוך fence מוגן מפני prompt injection.

### 02 — הפרדת כוונת העלאה/החלפה/מחיקה
* **סטטוס:** ✅ **תוקן**
* **ראיה בקוד:** [`runner.py:194-205`](backend/app/agent/runner.py#L194-L205) חוסם `delete_document` כשיש attachment. כמו כן הושלם מנגנון ה-Replace בצ'אט (ראו משימה A להלן).

### 03 — ג'וב שנכשל נשאר QUEUED לנצח
* **סטטוס:** ✅ **תוקן**
* **ראיה בקוד:** [`function_app.py:64-92`](worker/function_app.py#L64-L92) — טריגר על `index-jobs-poison` שמסמן את הג'וב כ-FAILED.

### 04 — לוגים של Backend לא מגיעים ל-App Insights
* **סטטוס:** ⚠️ **חלקי**
* **ראיה בקוד:** [`telemetry.py:125-142`](backend/app/core/telemetry.py#L125-L142) — קיים בקוד וממתין לחיבור `APPLICATIONINSIGHTS_CONNECTION_STRING` באינפרה.

### 05 — אין קונפיגורציה סמנטית באינדקס
* **סטטוס:** ⚠️ **ללא שינוי**
* **ראיה בקוד:** [`config.py:20`](backend/app/core/config.py#L20) — `azure_search_semantic_configuration_name: str = ""` (עובד כחיפוש היברידי, לא חוסם).

### 06 — אין ניקוי staging
* **סטטוס:** ✅ **תוקן**
* **ראיה בקוד:** [`dispatcher.py:63-64`](worker/services/dispatcher.py#L63-L64) ו-[`blob_service.py:125-152`](worker/services/blob_service.py#L125-L152) — מחיקת staging blob מתבצעת אך ורק לאחר הצלחת האינדוקס.

---

## מעקב משימות חיות (A עד G)

### ✅ משימות שכבר טופלו ובוצעו

#### ✅ A — "Document already exists" → החלפת מסמך (Replace Flow) בצ'אט
* **מה בוצע:** במקום לזרוק `ValueError`, המערכת ב-[`runner.py`](backend/app/agent/runner.py) מנתבת ישירות לבקשת אישור החלפה (`replace_document`) מהמשתמש.
* **מסלול:** `backend/**`

#### ✅ B — הנחיית "אין לי מידע" מפורשת ב-Prompt
* **מה בוצע:** ב-[`prompts.py`](backend/app/agent/prompts.py) הוגדרה הנחיה ברורה שכאשר אין מידע במסמך יש להשיב מפורשות "אין לי מידע בנושא" ולא להמציא או לנסות להעלות שוב.
* **מסלול:** `backend/**`

#### ✅ D — תזמון העלאת קבצים (Upload Timing)
* **מה בוצע:** ב-[`types.ts`](frontend/src/types.ts), [`useFileUpload.ts`](frontend/src/hooks/useFileUpload.ts), [`Composer.tsx`](frontend/src/components/Composer.tsx) ו-[`ChatWindow.tsx`](frontend/src/components/ChatWindow.tsx), קובץ שמצורף לצ'אט נשמר מקומית בזיכרון במצב `selected` ללא העלאה מוקדמת. ההעלאה בפועל ל-Storage מתבצעת אך ורק בלחיצה על "Send".
* **מסלול:** `frontend/**`

#### ✅ E — הצגת היסטוריית שיחות בממשק (Frontend Sidebar)
* **מה בוצע:** 
  * נוצר רכיב סרגל צד [ConversationSidebar.tsx](frontend/src/components/ConversationSidebar.tsx) המציג את היסטוריית השיחות (ממוינות מהחדשה לישנה עם כותרת וזמן יחסי), אפשרות למעבר בין שיחות, מחיקת שיחה, וכפתור לפתיחת שיחה חדשה.
  * ב-[`threads.ts`](frontend/src/lib/threads.ts) שמירת השיחות הועברה גם ל-`localStorage` (מעבר ל-sessionStorage), כך שהיסטוריית השיחות נשמרת ואינה נמחקת בסגירת הטאב.
  * ב-[`ChatWindow.tsx`](frontend/src/components/ChatWindow.tsx) חובר הסרגל לצד חלון הצ'אט עם כפתור Toggle לפתיחה והסתרה נוחה.
* **מסלול:** `frontend/**`

#### ✅ G — תיקון מחיקת צ'אנקים (Ghost Chunks)
* **מה בוצע:** ב-[`search_service.py`](worker/services/search_service.py) פונקציית `delete_document_chunks` עודכנה לתמוך במחיקה לפי `fileName eq '{file_name}'` (בנוסף ל-`parentDocumentId`). ב-[`dispatcher.py`](worker/services/dispatcher.py) הועבר שם הבלוב (`event.blob_name`) לפעולת המחיקה, כך שכל הצ'אנקים של המסמך נמחקים מיד מ-Azure AI Search ואין צ'אנקים רפאים.
* **מסלול:** `worker/**`

#### ✅ C — שדרוג חילוץ PDF (Document Intelligence)
* **מה בוצע:** ב-[`search_indexer.py`](worker/services/search_indexer.py) שולב `DocumentIntelligenceLayoutSkill` בתוך ה-Skillset לפני ה-`SplitSkill`, עם מיפוי של `layout_content` לתוך הפיצול, והוגדר `allowSkillsetToReadFileData: True` בפרמטרי האינדקסר לחילוץ איכותי, שומר עברית (RTL), טבלאות וסדר קריאה.
* **מסלול:** `worker/**`

---

## ריכוז סדר עדיפויות וסטטוס מעודכן

| # | משימה | חומרה | מסלול | סטטוס |
|---|-------|-------|-------|-------|
| 1 | **A — Replace flow בצ'אט** | 🔴 חוסם | `backend/**` | ✅ **בוצע** |
| 2 | **B — "אין לי מידע" מפורש** | 🔴 UX | `backend/**` | ✅ **בוצע** |
| 3 | **F — זיכרון Attachment מהיסטוריה** | 🔴 UX | `backend/**` | ✅ **בוצע, שונה** — ראו למטה |
| 4 | **D — תזמון העלאה ב-Composer** | 🟡 UX | `frontend/**` | ✅ **בוצע** |
| 5 | **E — היסטוריית שיחות בממשק** | 🟡 UX | `frontend/**` | ✅ **בוצע** |
| 6 | **G — תיקון מחיקת צ'אנקים (Ghost Chunks)** | 🔴 חוסם Data | `worker/**` | ✅ **בוצע** |
| 7 | **C — שדרוג חילוץ PDF (Document Intelligence)** | 🔴 איכות RAG | `worker/**` | ✅ **בוצע, תוקן** — ראו למטה |

---

## עדכון 2026-09-09 (ערב) — מיזוג + 3 באגים נוספים שנמצאו ותוקנו

**הקשר**: ה-push הזה (5f1c022) התנגש עם תיקון מקביל לאותו באג בדיוק (attachment שנעלם אם הסוכן שאל שאלת הבהרה לפני שפעל). מוזג — נשמרו A ו-B כמו שהם, **F הוחלף** במנגנון שכן מתנקה (`conversation_service.set/get/clear_pending_attachment`, לפי conversationId, ולא סריקת history שלא התאפסה לעולם — זו הייתה משאירה את המחיקה חסומה לצמיתות ברגע שקובץ כלשהו צורף פעם אחת בשיחה).

**גם ה-CI עצמו נכשל** ב-push המקורי (backend + worker) — 3 טסטים ישנים שלא עודכנו יחד עם השינוי בהתנהגות (assert על ההתנהגות הקודמת). כלומר עד לתיקון, שום דבר מה-push הזה לא היה חי בפועל.

**3 באגים אמיתיים נוספים נמצאו תוך כדי בדיקה חיה מול הפרודקשן (App Insights, לא רק CI ירוק):**

1. **מפתח מסמך ארוך מדי (>1024 תווים) לקבצים עם שם עברי ארוך.** `create_or_update_indexer` הסתמך על ה-mapping המרומז של Azure ל-`id` מ-`base64(metadata_storage_path)` — כתובת ה-URL המלאה, שם עברי מוחלף ב-percent-encoding (פי 6 לכל תו), ואז base64 מנפח עוד. תוקן: mapping מפורש מ-`metadata_storage_name` (שם הקובץ בלבד, לא ה-URL, ייחודי מטבעו בתוך container) — [`search_indexer.py`](worker/services/search_indexer.py).
2. **DocumentIntelligenceLayoutSkill נכשל על כל מסמך חדש** — לא היה משאב Document Intelligence בכלל ב-resource group, וה-skillset לא היה מחובר אליו. תוקן: משאב Cognitive Services רב-שירותי חדש ([`document_intelligence.bicep`](infrastructure/modules/document_intelligence.bicep)) + הרשאת Cognitive Services User לזהות המנוהלת של ה-Search + חיבור ה-skillset אליו דרך `AIServicesAccountIdentity` (בלי מפתח, כמו כל שאר המערכת) — [`search_indexer.py`](worker/services/search_indexer.py).
3. הקובץ "אישור לימודים 1125.pdf" מהדוח המקורי — אומת בפועל שהוא מאונדקס וניתן לחיפוש עכשיו.

**מסלול**: `backend/**`, `worker/**`, `infrastructure/**`.

