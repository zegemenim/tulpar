"""WhatsApp uçtan uca şifreli yedeğini (msgstore.db.crypt15) açar. 64 haneli anahtar gizli istemle sorulur;
ekrana, komut geçmişine veya diske yazılmaz. Kullanım: tulpar-yedek-ac"""
import getpass
import pathlib
import sqlite3
import sys
import zlib

from wa_crypt_tools.lib.db.dbfactory import DatabaseFactory
from wa_crypt_tools.lib.key.keyfactory import KeyFactory

Y = pathlib.Path.home() / "tulpar/veri/yedek"
GIRDI, CIKTI = Y / "msgstore.db.crypt15", Y / "msgstore.db"

if not GIRDI.exists():
    sys.exit(f"Yedek yok: {GIRDI}")
anahtar = getpass.getpass("64 haneli anahtar (boşluklu yazabilirsin, ekranda görünmez): ")
anahtar = "".join(c for c in anahtar.lower() if c in "0123456789abcdef")
if len(anahtar) != 64:
    sys.exit(f"Anahtar 64 karakter olmalı (girilen: {len(anahtar)}). Tekrar dene.")

key = KeyFactory.from_hex(anahtar)
del anahtar
with open(GIRDI, "rb") as f:
    db = DatabaseFactory.from_file(f)
    veri = db.decrypt(key, f.read())
try:
    veri = zlib.decompress(veri)
except zlib.error:
    sys.exit("Açılamadı: anahtar bu yedeğe ait değil gibi görünüyor. Anahtarı kontrol edip tekrar dene.")

CIKTI.touch(mode=0o600)
CIKTI.write_bytes(veri)
n = sqlite3.connect(CIKTI).execute("SELECT COUNT(*) FROM message").fetchone()[0]
print(f"Yedek açıldı: {n} mesaj. Claude'a haber verebilirsin.")
