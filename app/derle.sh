#!/bin/sh
# Yeni sürüm: versionCode'u artır, APK'yı derle, HP'ye yükle. Telefondaki uygulama "Güncelle" şeridini gösterir.
# Kullanım: ./derle.sh "kısa değişiklik notu"
set -e
cd "$(dirname "$0")"
export JAVA_HOME=${JAVA_HOME:-/opt/homebrew/opt/openjdk@17} ANDROID_HOME=${ANDROID_HOME:-$HOME/Library/Android/sdk}
SURUM=$(node -e "const f='app.json',d=require('./'+f);d.expo.android.versionCode=(d.expo.android.versionCode||1)+1;require('fs').writeFileSync(f,JSON.stringify(d,null,2)+'\n');console.log(d.expo.android.versionCode)")
echo "sürüm $SURUM derleniyor"
npx expo prebuild --platform android --no-install >/dev/null
grep -q "^org.gradle.workers.max" android/gradle.properties || printf "\norg.gradle.workers.max=3\n" >> android/gradle.properties
(cd android && nice -n 15 ./gradlew assembleRelease --no-daemon -q)
APK=android/app/build/outputs/apk/release/app-release.apk
mkdir -p ../dist && cp "$APK" ../dist/Tulpar.apk
printf '{"surum": %s, "tarih": "%s", "notlar": %s}\n' "$SURUM" "$(date +%Y-%m-%d)" "$(node -e 'console.log(JSON.stringify(process.argv[1]||""))' "$1")" > /tmp/surum.json
scp -q "$APK" tulpar:tulpar/veri/uygulama/Tulpar.apk.yeni
scp -q /tmp/surum.json tulpar:tulpar/veri/uygulama/surum.json.yeni
ssh -n tulpar 'cd ~/tulpar/veri/uygulama && mv Tulpar.apk.yeni Tulpar.apk && mv surum.json.yeni surum.json'
echo "sürüm $SURUM HP'ye yüklendi"
