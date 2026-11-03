// Telefonu uzaktan kontrol: HP'nin /cihaz/bekleyen/telefon sırasındaki komutları (ses, parlaklık, rahatsız etme, müzik)
// uygular. Komut döngüsü UyandirmaServisi içinden başlar (servis zaten sürekli çalışıyor). Parlaklık ve rahatsız etme için
// kullanıcının bir kez "Cihazlarım" ekranından izin vermesi gerekir.
const fs = require('fs');
const path = require('path');
const { withAndroidManifest, withDangerousMod } = require('expo/config-plugins');

const KOTLIN = (p) => `package ${p}

import android.app.NotificationManager
import android.app.SearchManager
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.provider.MediaStore
import android.provider.Settings
import android.util.Log
import android.view.KeyEvent
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

object CihazKomutu {
  @Volatile private var calisiyor = false

  fun baslat(ctx: Context) {
    if (calisiyor) return
    calisiyor = true
    Thread {
      while (true) {
        try { yokla(ctx.applicationContext) } catch (e: Exception) { Log.w("Tulpar", "cihaz komutu: " + e.message) }
        Thread.sleep(3000)
      }
    }.start()
  }

  private fun yokla(ctx: Context) {
    val ayar = File(ctx.filesDir, "sunucu.json")
    if (!ayar.exists()) return
    val j = JSONObject(ayar.readText())
    val adresler = j.getJSONArray("adresler")
    for (i in 0 until adresler.length()) {
      try {
        val b = URL(adresler.getString(i).trimEnd('/') + "/cihaz/bekleyen/telefon").openConnection() as HttpURLConnection
        b.connectTimeout = 3000; b.readTimeout = 4000
        b.setRequestProperty("x-tulpar-anahtar", j.getString("anahtar"))
        if (b.responseCode != 200) continue
        val liste = JSONArray(b.inputStream.bufferedReader().use { it.readText() })
        for (k in 0 until liste.length()) uygula(ctx, liste.getJSONObject(k))
        return
      } catch (e: Exception) { continue }
    }
  }

  private fun uygula(ctx: Context, k: JSONObject) {
    val ses = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    val adim = maxOf(1, ses.getStreamMaxVolume(AudioManager.STREAM_MUSIC) / 6)
    fun medya(tus: Int) {
      ses.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, tus)); ses.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, tus))
    }
    val deger = if (k.isNull("deger")) null else k.get("deger")
    when (val islem = k.getString("islem")) {
      "ses_ac" -> ses.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_RAISE, 0)
      "ses_kis" -> ses.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_LOWER, 0)
      "sessiz" -> ses.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_MUTE, 0)
      "ses_ayar" -> ses.setStreamVolume(AudioManager.STREAM_MUSIC, ses.getStreamMaxVolume(AudioManager.STREAM_MUSIC) * (deger.toString().toDoubleOrNull() ?: 50.0).toInt() / 100, 0)
      "medya_cal", "medya_dur" -> medya(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE)
      "medya_devam" -> medya(KeyEvent.KEYCODE_MEDIA_PLAY)
      "medya_sonraki" -> medya(KeyEvent.KEYCODE_MEDIA_NEXT)
      "medya_onceki" -> medya(KeyEvent.KEYCODE_MEDIA_PREVIOUS)
      "parlaklik_ac", "parlaklik_kis", "parlaklik_ayar" -> {
        if (!Settings.System.canWrite(ctx)) { Log.w("Tulpar", "parlaklık izni yok"); return }
        val simdi = Settings.System.getInt(ctx.contentResolver, Settings.System.SCREEN_BRIGHTNESS, 128)
        val yeni = when (islem) { "parlaklik_ac" -> simdi + 40; "parlaklik_kis" -> simdi - 40; else -> (deger.toString().toDoubleOrNull() ?: 50.0).toInt() * 255 / 100 }
        Settings.System.putInt(ctx.contentResolver, Settings.System.SCREEN_BRIGHTNESS_MODE, Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL)
        Settings.System.putInt(ctx.contentResolver, Settings.System.SCREEN_BRIGHTNESS, yeni.coerceIn(5, 255))
      }
      "rahatsiz_etme_ac", "rahatsiz_etme_kapat" -> {
        val nm = ctx.getSystemService(NotificationManager::class.java)
        if (!nm.isNotificationPolicyAccessGranted) { Log.w("Tulpar", "rahatsız etme izni yok"); return }
        nm.setInterruptionFilter(if (islem == "rahatsiz_etme_ac") NotificationManager.INTERRUPTION_FILTER_NONE else NotificationManager.INTERRUPTION_FILTER_ALL)
      }
      "sarki_cal" -> {  // arka plandan etkinlik başlatma kısıtlı olabilir; olmazsa komut sessizce düşer
        val i = Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH).setPackage("com.google.android.apps.youtube.music")
          .putExtra(SearchManager.QUERY, deger.toString()).putExtra(MediaStore.EXTRA_MEDIA_FOCUS, "vnd.android.cursor.item/*")
          .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(i)
      }
    }
  }
}
`;

module.exports = function cihaz(config) {
  const paket = config.android.package;
  config = withDangerousMod(config, ['android', async (c) => {
    const klasor = path.join(c.modRequest.platformProjectRoot, 'app/src/main/java', ...paket.split('.'));
    fs.mkdirSync(klasor, { recursive: true });
    fs.writeFileSync(path.join(klasor, 'CihazKomutu.kt'), KOTLIN(paket));
    return c;
  }]);
  return withAndroidManifest(config, (c) => {
    const m = c.modResults.manifest;
    m['uses-permission'] = m['uses-permission'] || [];
    for (const izin of ['android.permission.MODIFY_AUDIO_SETTINGS', 'android.permission.WRITE_SETTINGS', 'android.permission.ACCESS_NOTIFICATION_POLICY']) {
      if (!m['uses-permission'].some((x) => x.$['android:name'] === izin)) m['uses-permission'].push({ $: { 'android:name': izin } });
    }
    return c;
  });
};
