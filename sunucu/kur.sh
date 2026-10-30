#!/bin/sh
# Sunucu dosyalarını bu kullanıcıya göre kurar: systemd servisleri, terminal komutları, ayar örnekleri.
# Kullanım (sunucuda, repo kökünde): sh sunucu/kur.sh
set -e
K=$(id -un)
mkdir -p ~/tulpar/veri ~/tulpar/models
for f in sunucu/systemd/*.service; do
  sed "s/KULLANICI/$K/g" "$f" | sudo tee "/etc/systemd/system/$(basename "$f")" >/dev/null
done
for f in sunucu/*.env.ornek; do
  hedef=~/tulpar/models/$(basename "$f" .ornek)
  [ -f "$hedef" ] || sed "s/KULLANICI/$K/g" "$f" > "$hedef"
done
[ -f ~/tulpar/veri/sahip.json ] || cp sunucu/sahip.json.ornek ~/tulpar/veri/sahip.json
sudo install -m 755 sunucu/komutlar/* /usr/local/bin/
sudo systemctl daemon-reload
echo "Kuruldu. ~/tulpar/veri/sahip.json dosyasına kendi adını yaz."
