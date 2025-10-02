# Telegram Handlers - Smoke Test Guide

## Overview
Smoke test guide for verifying Telegram bot review handlers with Answer Engine (Stage 12).

---

## Prerequisites

1. **Bot Running**: `systemctl status sovani-bot` → active
2. **Database Migrated**: `alembic upgrade head` → applied `reply_text` migration
3. **Test Reviews in DB**: At least 3 pending reviews (short 5★, short 1★, long/media)
4. **Telegram Access**: Manager has access to bot via `/reviews` command

---

## Test Scenario 1: Typical Positive Review (5★, Short)

### Input
- Rating: 5★
- Text: "Супер!" (or empty)
- Media: No

### Expected Behavior
1. `/reviews` → Shows review with "📝 Сгенерировать ответ" button
2. Click "📝 Сгенерировать ответ"
   - Bot shows: "Готовлю драфт…"
   - Returns: **Template-based reply**
   - Contains: "SoVAni" brand mention
   - Does NOT contain: "покупатель"
   - Buttons: "✅ Отправить" + "🔄 Обновить драфт"
3. Click "✅ Отправить"
   - Bot shows: "✅ Ответ отправлен: [reply text]"
   - DB: `reply_status = 'sent'`, `reply_text` saved

### Verification
```sql
SELECT review_id, rating, text, reply_status, reply_text 
FROM reviews 
WHERE rating = 5 AND reply_status = 'sent' 
LIMIT 1;
```

**Metrics Check**:
```bash
curl http://localhost:8000/metrics | grep reviews_classified_total
# Should see: reviews_classified_total{marketplace="WB",classification="typical_positive"} 1

curl http://localhost:8000/metrics | grep reviews_processed_total
# Should see: reviews_processed_total{marketplace="WB",status="template"} 1
```

---

## Test Scenario 2: Typical Negative Review (1★, Short)

### Input
- Rating: 1★
- Text: "Маломерит" (or "Плохо", "Брак")
- Media: No

### Expected Behavior
1. `/reviews` → Shows review
2. Click "📝 Сгенерировать ответ"
   - Returns: **Negative template** (apologetic tone)
   - Contains: "SoVAni", no "покупатель"
   - Mentions: размерная сетка / помощь / обмен
3. Click "✅ Отправить"
   - Saved as sent

### Verification
- Check reply_text does NOT say "Спасибо за ваш отзыв! ❤️" (positive)
- Should have apologetic/helpful tone
- Metrics: `classification="typical_negative"`, `status="template"`

---

## Test Scenario 3: Atypical Review (Long or Media)

### Input
- Rating: 4★
- Text: "Очень понравилось качество ткани, быстрая доставка, хороший размер!" (>40 chars)
- Media: No (or Yes for media test)

### Expected Behavior
1. `/reviews` → Shows review
2. Click "📝 Сгенерировать ответ"
   - Returns: **AI-generated reply** (OpenAI)
   - Contains: "SoVAni", no "покупатель"
   - Tone: matches rating (4★ = positive but acknowledges)
   - If has media: acknowledges photo/video
3. Click "🔄 Обновить драфт"
   - Regenerates reply (may differ slightly)
4. Click "✅ Отправить"
   - Saved as sent

### Verification
- Check logs for "Using AI for..." message
- Metrics: `classification="atypical"`, `status="custom_ai"`

---

## Test Scenario 4: Name Personalization (Future)

**Current State**: Name extraction not yet implemented (TODO in code).

### Expected Behavior (When Implemented)
- Review with customer name "Анна"
- Draft reply starts with: "Анна, спасибо..."
- NOT: "Покупатель Анна,..." or "Уважаемый покупатель,..."

---

## Quality Checklist

After running all scenarios, verify:

- [ ] ✅ **No "покупатель" word** in ANY reply (templates or AI)
- [ ] ✅ **SoVAni brand** mentioned in ALL replies
- [ ] ✅ **Correct tone** for rating (5★ = happy, 1★ = apologetic, 3★ = neutral)
- [ ] ✅ **Template vs AI** decision correct:
  - Short (<40 chars) + no media → Template
  - Long (>40 chars) OR has media → AI
- [ ] ✅ **Name personalization** works (if name available)
- [ ] ✅ **Idempotent send**: Clicking send twice doesn't break
- [ ] ✅ **Logs have request_id** for correlation
- [ ] ✅ **Metrics updated** (`/metrics` shows increments)
- [ ] ✅ **No blocking errors** if WB/Ozon API unavailable

---

## Metrics Validation

### Expected Metrics After Tests

```bash
# Classification metrics (by type)
reviews_classified_total{marketplace="WB",classification="typical_positive"} 1+
reviews_classified_total{marketplace="WB",classification="typical_negative"} 1+
reviews_classified_total{marketplace="WB",classification="atypical"} 1+

# Processing metrics (template vs AI)
reviews_processed_total{marketplace="WB",status="template"} 2+
reviews_processed_total{marketplace="WB",status="custom_ai"} 1+
```

### Alerting Thresholds (Future)
- If `atypical > 30%` of total → investigate (too many long reviews or media)
- If `custom_ai` fails → fallback to template (already implemented)

---

## Log Correlation Example

```json
{
  "timestamp": "2025-10-02T10:30:00Z",
  "level": "INFO",
  "logger": "sovani_bot.tg.reviews",
  "message": "Review classified: wb_12345 → typical_positive (rating=5, text_len=6, has_media=False)",
  "request_id": "abc123-def456",
  "module": "reviews_service"
}
```

All logs for single request share same `request_id` → easy debugging.

---

## Common Issues

### Issue: "Готовлю драфт…" but no reply
- **Cause**: OpenAI API error (atypical review)
- **Expected**: Fallback to template-based reply
- **Check**: Logs for "AI generation failed, using fallback"

### Issue: Reply contains "покупатель"
- **Cause**: Template bug or AI prompt failure
- **Action**: File bug, check template files `app/domain/reviews/templates.py`

### Issue: Wrong tone (5★ gets negative reply)
- **Cause**: Classification bug
- **Check**: Logs for classification result
- **Action**: Review `app/domain/reviews/classifier.py` logic

---

## Success Criteria

✅ All 3 scenarios work end-to-end  
✅ Zero "покупатель" mentions  
✅ Metrics show correct classification/processing splits  
✅ Logs have correlation IDs  
✅ No crashes or blocking errors  

**Stage 12 Telegram Integration: COMPLETE** 🎉
