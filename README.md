# 🔐 LockFace — Gerçek Zamanlı Yüz Tanıma Tabanlı Bilgisayar Güvenlik Sistemi

LockFace, Python ile geliştirilmiş gerçek zamanlı bir biyometrik kimlik doğrulama uygulamasıdır.
Uygulama, bilgisayarın kullanılmasına izin vermeden önce web kamerası aracılığıyla kullanıcının kimliğini doğrular.

Bu proje, yüz tanıma + canlılık tespiti + sahtecilik önleme tekniklerini birleştirerek **Windows Hello benzeri yazılımsal bir güvenlik katmanı** oluşturmayı amaçlamaktadır.

---
## 📖 Bu Proje Neden Var?

Günümüzde dizüstü bilgisayarların yalnızca bir kısmı donanımsal biyometrik doğrulama (örneğin Windows Hello IR kamera) desteği sunmaktadır.
Ancak çoğu kullanıcı hâlâ yalnızca parola veya PIN ile bilgisayarını korumaktadır.

Bu durum bazı önemli güvenlik sorunları doğurur:

* Bilgisayar başında unutulan açık oturumlar
* Ortak kullanım alanlarında (yurt, kütüphane, ofis) izinsiz erişim
* Şifrenin görülmesi veya tahmin edilmesi
* Fiziksel erişimi olan birinin cihazı kolayca kullanabilmesi

Aslında kullanıcıların önemli bir kısmı biyometrik güvenlik ister;
fakat bilgisayarlarında yüz tanıma donanımı bulunmadığı için bunu kullanamaz.

**LockFace projesi tam olarak bu boşluğu doldurmak için geliştirildi.**

Amaç, özel bir donanım gerektirmeden, yalnızca standart bir web kamerası kullanarak
herhangi bir bilgisayara yazılımsal bir biyometrik güvenlik katmanı kazandırmaktır.

Yani proje şu soruya çözüm üretir:

> “Yüz tanıma özelliği olmayan bilgisayarlarda biyometrik güvenlik nasıl sağlanabilir?”

LockFace, bilgisayarın başına geçen kişinin gerçekten kayıtlı kullanıcı olup olmadığını kontrol eder.
Kullanıcı doğrulanamazsa sistem otomatik olarak Windows’u kilitler.

Bu sayede:

* Açık unutulan bilgisayarlar korunur
* Yetkisiz fiziksel erişim engellenir
* Parola güvenliğine ek bir katman eklenir

---

## 🧪 Gerçek Hayat Senaryosu

Bir öğrenci kütüphanede çalışırken bilgisayarını birkaç dakika masada bırakır.

Normal durumda:
→ Bilgisayarı açık bulan biri cihazı kullanabilir.

LockFace aktifken:
→ Sistem kameradan yeni yüzü algılar
→ Kullanıcı doğrulanamaz
→ Windows otomatik olarak kilitlenir.

Kullanıcı geri döndüğünde yüzü doğrulanır ve erişim tekrar sağlanır.

---

## 💻 Otomatik Başlatma (Bilgisayar Açılır Açılmaz Çalıştırma)

LockFace, kullanıcı isterse bilgisayar açıldığında otomatik olarak çalışacak şekilde ayarlanabilir.
Böylece sistem her oturumda manuel olarak başlatılmak zorunda kalmaz.

### Windows Başlangıca Ekleme

1. **Win + R** tuşlarına bas
2. Açılan pencereye yaz:

```
shell:startup
```

3. Açılan klasör, Windows başlangıç klasörüdür.

4. Proje klasöründe bulunan `main.pyw` dosyasına sağ tık → **Kısayol oluştur**

5. Oluşturulan kısayolu bu klasöre kopyala.

Artık bilgisayar açıldığında LockFace otomatik çalışacaktır.

> Not: `main.pyw` uzantısı sayesinde program arka planda çalışır ve terminal penceresi açılmaz.

---

## 🔐 Güvenlik Notu

Bu proje işletim sisteminin yerleşik kimlik doğrulamasını değiştirmez.
LockFace, Windows güvenliğini devre dışı bırakmaz;
yalnızca bilgisayar kullanımına ek bir koruma katmanı sağlar.

Yani sistem, Windows Hello yerine değil, **Windows güvenliğine ek olarak** çalışmak üzere tasarlanmıştır.


## 🎯 Projenin Amacı

Geleneksel parola tabanlı güvenlik sistemleri aşağıdaki risklere açıktır:

* Parola tahmini (brute force)
* Omuz üstü izleme (shoulder surfing)
* Şifre sızıntıları
* Bilgisayara fiziksel erişim

LockFace, bilgisayarın yetkisiz kişiler tarafından kullanılmasını önlemek için **biyometrik doğrulama katmanı** sağlar ve doğrulama başarısız olursa sistemi kilitler.

---

## 🧠 Temel Özellikler

### 👤 Yüz Tanıma

* `face_recognition` (dlib 128-boyut yüz embeddingleri) kullanır
* Kayıt sırasında **5 farklı yüz örneği** alınır
* Çoklu örnek doğrulama (voting sistemi)
* Sıkı benzerlik eşikleri ile yanlış kabulü engeller

---

### 👀 Canlılık Tespiti (Anti-Spoof)

Fotoğraf veya ekran ile sistemi kandırmayı önlemek için:

* Göz kırpma tespiti (Eye Aspect Ratio - EAR)
* Çoklu kare doğrulama
* Sürekli yüz takibi
* Yüz boyutu kontrolü
* Bulanıklık (blur) kontrolü

Bu sayede şu saldırılar engellenir:

* Basılı fotoğraf
* Telefon ekranı
* Statik görüntü

---

### 🛡 Güvenlik Mantığı

Sistemin bilgisayarı açması için **tüm şartların sağlanması gerekir:**

1. Yüz algılanmalı
2. Görüntü kalitesi yeterli olmalı
3. Kullanıcı göz kırpmalı
4. 5 kayıt örneğinden en az **2 tanesi güçlü eşleşmeli**
5. **7 ardışık karede doğrulama sağlanmalı**

Doğrulama başarısız olursa:
→ Windows otomatik olarak kilitlenir.

---

### 🔁 Kurtarma Sistemi

Olası hatalara karşı güvenli bir kurtarma mekanizması bulunur:

* İlk çalıştırmada rastgele **11 haneli kurtarma kodu** üretilir
* Kod SHA-256 + salt ile şifrelenerek saklanır
* 3 hatalı girişte geçici kilit uygulanır
* Verileri sıfırlamaya izin verir (güvenliği atlatmaz)

---

## 🏗 Sistem Mimarisi

```
Webcam → Yüz Algılama → Landmark Çıkarma → Göz Kırpma Kontrolü
       → Kalite Filtreleri → Encoding Karşılaştırma → Voting Sistemi
       → Çoklu Kare Doğrulama → Erişim / Windows Kilidi
```

---

## 🛠 Kullanılan Teknolojiler

| Teknoloji        | Amaç                          |
| ---------------- | ----------------------------- |
| Python           | Ana programlama dili          |
| OpenCV           | Kamera ve görüntü işleme      |
| dlib             | Yüz embedding üretimi         |
| face_recognition | Yüz karşılaştırma             |
| NumPy            | Sayısal işlemler              |
| SHA-256          | Güvenli kurtarma kodu saklama |

---

## ⚙️ Kurulum

### 1) Depoyu klonla

```bash
git clone https://github.com/KULLANICI_ADIN/LockFace.git
cd LockFace
```

### 2) Gerekli kütüphaneleri yükle

(Python 3.10 veya 3.11 önerilir)

```bash
pip install -r requirements.txt
```

---

## ▶️ İlk Çalıştırma (Kayıt Alma)

Programı çalıştır:

```bash
python main.pyw
```

İlk çalıştırmada:

* Kamera otomatik açılır
* Sistem **5 yüz örneği** alır
* Her örnek için göz kırpman istenir
* Kurtarma kodu oluşturulur

Yüz verileri `data_secure/` klasöründe **yerel olarak saklanır**.

⚠️ Bu klasör biyometrik veri içerdiği için GitHub’a yüklenmez.

---

## 🔐 Doğrulama Süreci

1. Kamera açılır
2. Yüz algılanır
3. Kullanıcı göz kırpar
4. Görüntü kalitesi kontrol edilir
5. Encoding karşılaştırması yapılır
6. Çoklu kare doğrulaması gerçekleştirilir
7. Erişim verilir veya Windows kilitlenir

---

## 📊 Sahtecilik Koruması

| Saldırı Türü     | Sonuç                 |
| ---------------- | --------------------- |
| Basılı fotoğraf  | Reddedilir            |
| Telefon ekranı   | Genellikle reddedilir |
| Statik görüntü   | Reddedilir            |
| Gerçek kullanıcı | Kabul edilir          |

---

## 🧩 Proje Yapısı

```
LockFace/
│
├── main.pyw
├── requirements.txt
├── README.md
├── .gitignore
│
└── data_secure/   (otomatik oluşur)
    ├── face_encoding.pkl
    ├── rescue.json
    └── faces/
```

---

## ⚠️ Önemli Notlar

* Proje hiçbir biyometrik veriyi internete göndermez
* Tüm yüz verileri yalnızca yerel bilgisayarda saklanır
* `data_secure/` klasörü silinirse sistem sıfırlanır

---

## 🚀 Gelecek Geliştirmeler

* Baş hareketi challenge (anti-replay)
* Grafik arayüz (GUI)
* Çoklu kullanıcı desteği
* Linux desteği
* Mobil cihaz ile uzaktan kilit açma

---

## 👨‍💻 Geliştirici

**Görkem Topal**
Bilgisayar Mühendisliği Öğrencisi

---

## 📜 Lisans

Bu proje eğitim ve araştırma amaçlı geliştirilmiştir.
