# Bilgin Travel — Tedarikçi Entegrasyon Rehberi

Bu rehber, otel, uçuş ve tur operatörlerinin Bilgin Travel platformuna API üzerinden bağlanmasını açıklar. Entegrasyon süreci üç aşamadan oluşur: kimlik doğrulama, envanter senkronizasyonu ve rezervasyon yönetimi.

---

## Genel Mimari

Bilgin Travel, tedarikçilerle **REST API** ve **webhook** kombinasyonu üzerinden çalışır:

- Tedarikçi → Bilgin Travel: envanter ve fiyat güncellemeleri (push veya pull).
- Bilgin Travel → Tedarikçi: rezervasyon onayı, değişiklik ve iptal bildirimleri (webhook).

Tüm API trafiği HTTPS üzerinden şifrelenir. JSON veri formatı kullanılır; karakter seti UTF-8'dir.

---

## Kimlik Doğrulama

### API Anahtarı Edinme

Tedarikçi portalı (portal.bilgintravel.com.tr/suppliers) üzerinden kayıt yaptırın. Onay sürecinde aşağıdaki bilgiler istenir:

- Şirket vergi numarası ve ticaret sicil belgesi
- Ürün tipi (otel / uçuş / tur paketi / transfer)
- Beklenen günlük istek hacmi (yaklaşık)

Onay sonrası her ortam için ayrı anahtar tanımlanır:

| Ortam | Base URL |
|---|---|
| Sandbox | `https://api-sandbox.bilgintravel.com.tr/v2` |
| Production | `https://api.bilgintravel.com.tr/v2` |

### İstek Başlıkları

```
Authorization: Bearer <API_KEY>
Content-Type: application/json
X-Supplier-Id: <SUPPLIER_ID>
```

`X-Supplier-Id`, tedarikçi portalında görüntülenen sabit tanımlayıcıdır. Eksik ya da hatalı başlıklar `401 Unauthorized` döndürür.

### Rate Limiting

Sandbox ortamında dakikada 60 istek, production ortamında dakikada 600 istek sınırı uygulanır. Aşıldığında `429 Too Many Requests` yanıtı alırsınız; yanıt başlığındaki `Retry-After` değerine göre beklemeniz gerekir.

---

## Envanter Senkronizasyonu

### Otel Envanteri

#### Pull Modeli (Tercih Edilen)

Bilgin Travel, tedarikçi endpoint'ini belirli aralıklarda çeker:

```
GET /inventory/hotels/{hotel_id}/availability?check_in=YYYY-MM-DD&check_out=YYYY-MM-DD
```

Yanıt örneği:

```json
{
  "hotel_id": "HTL-00421",
  "rooms": [
    {
      "room_type_id": "DBL-STD",
      "available_count": 12,
      "rate_plans": [
        { "plan_id": "BB", "price_per_night": 1250.00, "currency": "TRY" },
        { "plan_id": "HB", "price_per_night": 1750.00, "currency": "TRY" }
      ]
    }
  ]
}
```

#### Push Modeli

Tedarikçi, fiyat veya müsaitlik değişikliğinde Bilgin Travel'a bildirim gönderir:

```
POST https://api.bilgintravel.com.tr/v2/inventory/push
```

İstek gövdesi, pull modeliyle aynı yapıyı taşır. Kısa süredeki toplu güncellemeler için batch endpoint kullanılır (maksimum 500 kayıt / istek).

### Uçuş Envanteri

Uçuş envanteri GDS (Global Distribution System) bağlantısı veya doğrudan havayolu API'si üzerinden senkronize edilir. Bilgin Travel, IATA standartlarına uygun NDC (New Distribution Capability) formatını destekler.

---

## Rezervasyon Yönetimi

### Rezervasyon Oluşturma

```
POST /bookings
```

Gövde:

```json
{
  "supplier_product_id": "HTL-00421:DBL-STD:BB",
  "check_in": "2026-08-15",
  "check_out": "2026-08-18",
  "guests": [
    { "first_name": "Ayşe", "last_name": "Yılmaz", "type": "adult" }
  ],
  "contact_email": "ayseyilmaz@example.com",
  "idempotency_key": "uuid-v4-buraya"
}
```

`idempotency_key` zorunludur; aynı anahtarla yapılan tekrar istekleri yeni rezervasyon oluşturmaz, ilk yanıtı döndürür. Ağ hatalarında güvenli yeniden denemeyi sağlar.

Başarılı yanıt:

```json
{
  "booking_id": "ATL-20260715-0042",
  "status": "confirmed",
  "confirmation_code": "SUPPL-XYZ-9912"
}
```

### Rezervasyon Sorgulama

```
GET /bookings/{booking_id}
```

### İptal

```
DELETE /bookings/{booking_id}
```

İptal edilebilirlik ve kesinti oranı yanıtta `cancellation_policy` alanında döner; uygulamak için ayrı bir `POST /bookings/{booking_id}/cancel` çağrısı yapılır.

---

## Webhook Bildirimleri

Bilgin Travel, tedarikçi sistemine aşağıdaki olayları bildirir:

| Olay | Tetikleyici |
|---|---|
| `booking.created` | Müşteri rezervasyon tamamladığında |
| `booking.modified` | Tarih veya kişi değişikliği yapıldığında |
| `booking.cancelled` | İptal onaylandığında |
| `payment.received` | Ödeme başarılı olduğunda |

### Webhook Kaydı

Tedarikçi portalından endpoint URL'nizi girin. Her bildirim `X-Bilgin-Signature` başlığı içerir; imzayı `HMAC-SHA256(secret, payload)` ile doğrulayın.

### Başarısız Bildirimler

Endpoint'iniz `2xx` dışında yanıt verirse Bilgin Travel üstel geri çekilmeyle (1s, 5s, 30s, 5m, 30m) toplam 5 kez yeniden dener. 5 denemeden sonra başarısız kalan bildirimler tedarikçi portalında listelenir.

---

## Hata Kodları

| HTTP Kodu | Bilgin Kodu | Açıklama |
|---|---|---|
| 400 | `INVALID_REQUEST` | Eksik ya da hatalı alan |
| 401 | `UNAUTHORIZED` | Geçersiz API anahtarı |
| 404 | `NOT_FOUND` | Ürün veya rezervasyon bulunamadı |
| 409 | `ALREADY_EXISTS` | Aynı idempotency_key'le farklı gövde |
| 422 | `UNAVAILABLE` | İstenen tarihte müsaitlik yok |
| 429 | `RATE_LIMITED` | İstek limiti aşıldı |
| 500 | `INTERNAL_ERROR` | Bilgin sunucu hatası |

---

## Test Ortamı

Sandbox'ta gerçek ödeme yapılmaz. Test kartı: `4242 4242 4242 4242`, son kullanma: gelecek herhangi bir tarih, CVV: `123`.

Sandbox'ta tanımlı birkaç test oteli bulunur (HTL-TEST-001 – HTL-TEST-010). Bu oteller her gece sıfırlanır; üretim verisi içermez.

Entegrasyon onayı için en az şu senaryoların sandbox'ta başarıyla tamamlanması gerekir:

1. Müsaitlik sorgulama
2. Rezervasyon oluşturma (idempotency testi dahil)
3. Rezervasyon iptali ve webhook alımı
4. Rate limit aşımı senaryosu (429 işlemi)
