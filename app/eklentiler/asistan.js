// Android'de Tulpar'ı "dijital asistan" olarak seçilebilir yapar: güç/ana ekran tuşuna basılı tutunca açılır.
// Asistan isteği (ASSIST/VOICE_COMMAND) ayrı, görünmez bir AsistanActivity'ye gelir; o da uygulamayı
// tulpar://dinle bağlantısıyla açar. Böylece uygulama "elle mi açıldı, asistan olarak mı" ayırt eder ve
// sadece asistan olarak açılınca dinlemeye başlar.
const fs = require('fs');
const path = require('path');
const { withAndroidManifest, withDangerousMod } = require('expo/config-plugins');

const KOTLIN = (paket) => `package ${paket}

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle

class AsistanActivity : Activity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    // Uygulama kapalıysa tulpar://dinle bağlantısı açılışta kaybolabiliyor: istek dosyaya da yazılır, ana ekran okur
    java.io.File(filesDir, "dinle_istegi").writeText(System.currentTimeMillis().toString())
    // Uyandırma servisi mikrofonu tutuyorsa bırakmasını iste (yoksa uygulamanın mikrofonu boş kalır)
    if (java.io.File(filesDir, "uyandirma_acik").exists()) {
      startForegroundService(Intent(this, UyandirmaServisi::class.java).putExtra("ogren", "duraklat"))
    }
    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("tulpar://dinle"), this, MainActivity::class.java)
      .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP))
    finish()
  }
}
`;

module.exports = function asistan(config) {
  const paket = config.android.package;
  config = withDangerousMod(config, ['android', async (c) => {
    const klasor = path.join(c.modRequest.platformProjectRoot, 'app/src/main/java', ...paket.split('.'));
    fs.mkdirSync(klasor, { recursive: true });
    fs.writeFileSync(path.join(klasor, 'AsistanActivity.kt'), KOTLIN(paket));
    return c;
  }]);
  return withAndroidManifest(config, (c) => {
    const app = c.modResults.manifest.application[0];
    // eski sürümde ASSIST ana etkinlikteydi: kaldır
    const ana = app.activity.find((a) => a.$['android:name'] === '.MainActivity');
    ana['intent-filter'] = (ana['intent-filter'] || []).filter(
      (f) => !(f.action || []).some((x) => x.$['android:name'] === 'android.intent.action.ASSIST'));
    if (!app.activity.some((a) => a.$['android:name'] === '.AsistanActivity')) {
      app.activity.push({
        $: { 'android:name': '.AsistanActivity', 'android:exported': 'true', 'android:excludeFromRecents': 'true',
          'android:theme': '@android:style/Theme.Translucent.NoTitleBar', 'android:noHistory': 'true' },
        'intent-filter': [{
          action: [{ $: { 'android:name': 'android.intent.action.ASSIST' } }, { $: { 'android:name': 'android.intent.action.VOICE_COMMAND' } }],
          category: [{ $: { 'android:name': 'android.intent.category.DEFAULT' } }],
        }],
      });
    }
    return c;
  });
};
