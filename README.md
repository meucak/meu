# `meu` — MEU Evrensel Paket ve Proje Yöneticisi

**Windows 10/11** ve **Linux** üzerinde GitHub'daki (`meucak`) tüm projeleri tek terminal komutuyla indirip kuran, bağımlılıkları izole `.venv` ortamında hazırlayan, komutları `PATH`'e kaydeden ve masaüstü kısayolu oluşturan sıfır-bağımlılıklı CLI paket yöneticisi.

## Öne Çıkan Özellikler

- **Tek Komutla Kurulum:** İster sadece proje adı yazın (`meu install recep`), ister tam GitHub bağlantısı verin (`meu install github.com/meucak/recep`).
- **Çapraz Platform (Windows 10 & Linux):** Harici Python paketi gerektirmez (saf Python 3.8+ standart kütüphanesi). Windows'ta `.cmd`, `.ps1` ve masaüstü `.lnk` kısayolu; Linux'ta `~/.local/bin` çalıştırıcıları ve `.desktop` kaydı üretir.
- **Akıllı Proje Algılama & Uyumluluk Motoru:**
  - `sortingen`, `perf` gibi CLI araçlarını doğrudan terminal komutuna dönüştürür.
  - `recep`, `toshi-camera` gibi PyQt6 GUI uygulamaları için izole `.venv` kurar; `recep` için Windows `winsound` / `fcntl` / yerel cilt & ses uyarlamalarını otomatik uygular.
  - `borfek`, `tessera`, `fil`, `fleet-deck`, `kush` gibi Docker / web servisleri için başlatıcı kısayolları ve isteğe bağlı `--docker` ile ayağa kaldırma sunar.
  - Kataloğa sonradan eklenecek yeni `meucak` repolarını sezgisel olarak otomatik algılar (`meu.json` varsa önceliklendirir).
- **Git Olmadan da Çalışır:** Sistemde `git` kuruluysa `git clone --depth 1` kullanır; `git` yoksa otomatik olarak GitHub ZIP arşivi indirip çıkarır.

---

## `meu` Kurulumu

### `pip` ile Evrensel Kurulum (Windows 10 / 11 & Linux)
```bash
# PyPI üzerinden (yayınlandığında):
pip install meucak

# Doğrudan GitHub üzerinden (her zaman anında çalışır):
pip install git+https://github.com/meucak/meu.git
```
*(Kurulum sonrasında `meu`, `meucak` ve `meuget` komutlarının tamamı aynı aracı çalıştırır.)*

### Linux (Betik ile)
```bash
git clone https://github.com/meucak/meu.git && cd meu && ./install.sh
```
veya tek satırda:
```bash
curl -fsSL https://raw.githubusercontent.com/meucak/meu/main/install.sh | bash
```

### Windows 10 / 11 (PowerShell)
```powershell
git clone https://github.com/meucak/meu.git; cd meu; .\install.ps1
```
veya tek satırda:
```powershell
irm https://raw.githubusercontent.com/meucak/meu/main/install.ps1 | iex
```
*(Alternatif olarak `install.bat` dosyasına çift tıklayabilirsiniz. Kurulum `%USERPROFILE%\.meu\bin` klasörünü kullanıcı `PATH` değişkenine otomatik ekler.)*

---

## Kullanım Örnekleri

```bash
# Proje adıyla doğrudan kur (varsayılan sahip: meucak)
meu install recep
meu install sortingen
meu install perf

# GitHub bağlantısıyla kur
meu install github.com/meucak/recep
meu install https://github.com/meucak/borfek

# Kısa adlarla (alias) veya çoklu kur
meu install kamera
meu install aura-lan
meu install sortingen recep

# Docker servisi varsa konteynerleri de ayağa kaldırarak kur
meu install borfek --docker

# Kurulu değilse otomatik kurup hemen çalıştır
meu run sortingen --help

# Mevcut meucak projelerini listele / ara
meu search
meu info recep

# Kurulu uygulamaları gör, güncelle veya tamamen kaldır
meu list
meu update --all
meu uninstall recep

# Sistem sağlığını ve PATH durumunu denetle / onar
meu doctor --fix
```

*(Türkçe komut takma adları da desteklenir: `meu kur`, `meu sil`, `meu guncelle`, `meu liste`, `meu ara`, `meu bilgi`, `meu calistir`, `meu kontrol`.)*

---

## Testleri Çalıştırma

```bash
python3 -m unittest discover -s tests -v
```
