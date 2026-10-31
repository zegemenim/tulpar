// "Tulpar" / "Kâhya" ile uyandırma: telefonda ÇEVRİMDIŞI çalışan küçük bir Türkçe ses tanıyıcı (Vosk) arka planda
// sadece bu kelimeleri arar; ses hiçbir yere gönderilmez. Duyunca asistanı açar (tulpar://dinle).
// Uygulama ayarlarından UyandirmaActivity ile açılıp kapanır. Android gereği kalıcı bildirim gösterir.
const fs = require('fs');
const path = require('path');
const { withAndroidManifest, withAppBuildGradle, withDangerousMod } = require('expo/config-plugins');

const MODEL_URL = 'https://alphacephei.com/vosk/models/vosk-model-small-tr-0.3.zip';
const MODEL_KLASOR = 'vosk-model-small-tr-0.3';

const SERVIS = (p) => `package ${p}

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import java.io.File
import java.net.URL
import java.util.zip.ZipInputStream

class UyandirmaServisi : Service(), RecognitionListener {
  private var konusma: SpeechService? = null
  private var model: Model? = null
  private val ana = Handler(Looper.getMainLooper())
  private val kelime = Regex("\\\\b(tulpar|tul par|tülpar|kahya|kâhya|kah ya)\\\\b", RegexOption.IGNORE_CASE)

  override fun onBind(intent: Intent?): IBinder? = null

  private var modelAdresi: String? = null

  override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    intent?.getStringExtra("model_url")?.let { modelAdresi = it }
    return START_STICKY
  }

  override fun onCreate() {
    super.onCreate()
    bildirim("Ses modeli hazırlanıyor…")
    ana.postDelayed({ Thread { hazirla() }.start() }, 500)  // önce model adresi gelsin
  }

  private fun bildirim(metin: String) {
    val nm = getSystemService(NotificationManager::class.java)
    nm.createNotificationChannel(NotificationChannel("uyandirma", "Tulpar dinliyor", NotificationManager.IMPORTANCE_LOW))
    val ac = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
    val n = Notification.Builder(this, "uyandirma").setContentTitle("Tulpar dinliyor").setContentText(metin)
      .setSmallIcon(android.R.drawable.ic_btn_speak_now).setOngoing(true).setContentIntent(ac).build()
    if (Build.VERSION.SDK_INT >= 30) startForeground(41, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
    else startForeground(41, n)
  }

  private fun hazirla() {
    try {
      val klasor = File(filesDir, "${MODEL_KLASOR}")
      if (!File(klasor, "conf").exists()) {
        ana.post { bildirim("Türkçe ses modeli indiriliyor (37 MB, bir kez)…") }
        // önce uygulamanın HP'den indirdiği kopya (files/vosk-tr.zip), yoksa internetten
        val yerel = File(filesDir, "vosk-tr.zip")
        val kaynak = if (yerel.exists()) yerel.inputStream() else URL("${MODEL_URL}").openStream()
        ZipInputStream(kaynak).use { zip ->
          var g = zip.nextEntry
          while (g != null) {
            val hedef = File(filesDir, g.name)
            if (!hedef.canonicalPath.startsWith(filesDir.canonicalPath)) throw SecurityException("zip yolu")
            if (g.isDirectory) hedef.mkdirs() else { hedef.parentFile?.mkdirs(); hedef.outputStream().use { zip.copyTo(it) } }
            g = zip.nextEntry
          }
        }
        yerel.delete()
      }
      model = Model(klasor.absolutePath)
      ana.post { dinle() }
    } catch (e: Exception) {
      Log.e("Tulpar", "uyandirma modeli", e)
      ana.post { bildirim("Ses modeli hazırlanamadı, 1 dk sonra tekrar denenecek: " + e.message) }
      ana.postDelayed({ Thread { hazirla() }.start() }, 60000)
    }
  }

  private fun dinle() {
    val m = model ?: return
    try {
      konusma = SpeechService(Recognizer(m, 16000f), 16000f).also { it.startListening(this) }
      bildirim("“Tulpar” ya da “Kâhya” de")
    } catch (e: Exception) {
      Log.e("Tulpar", "dinleme baslamadi", e)
      ana.postDelayed({ dinle() }, 10000)  // mikrofon başka uygulamadaysa sonra tekrar dene
    }
  }

  private fun durdur() { konusma?.stop(); konusma?.shutdown(); konusma = null }

  private fun kontrol(hipotez: String?) {
    if (hipotez == null || konusma == null) return
    val j = JSONObject(hipotez)
    val metin = j.optString("partial", j.optString("text", ""))
    if (!kelime.containsMatchIn(metin)) return
    durdur()  // mikrofonu uygulamaya bırak
    startActivity(Intent(this, AsistanActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    ana.postDelayed({ dinle() }, 45000)
  }

  override fun onPartialResult(h: String?) = kontrol(h)
  override fun onResult(h: String?) = kontrol(h)
  override fun onFinalResult(h: String?) = kontrol(h)
  override fun onError(e: Exception?) { durdur(); ana.postDelayed({ dinle() }, 5000) }
  override fun onTimeout() { durdur(); dinle() }

  override fun onDestroy() { ana.removeCallbacksAndMessages(null); durdur(); model?.close(); super.onDestroy() }
}
`;

const ACTIVITY = (p) => `package ${p}

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings

// Ayarlardaki anahtardan çağrılır: islem=ac | kapat. Gerekirse "diğer uygulamaların üzerinde göster" iznini ister
// (Android, arka plandan uygulama açmak için bunu şart koşuyor).
class UyandirmaActivity : Activity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    val servis = Intent(this, UyandirmaServisi::class.java)
    intent.getStringExtra("model_url")?.let { servis.putExtra("model_url", it) }
    if (intent.getStringExtra("islem") == "kapat") {
      stopService(servis)
    } else {
      if (!Settings.canDrawOverlays(this)) {
        startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + packageName)))
      }
      startForegroundService(servis)
    }
    finish()
  }
}
`;

module.exports = function uyandirma(config) {
  const paket = config.android.package;
  config = withDangerousMod(config, ['android', async (c) => {
    const klasor = path.join(c.modRequest.platformProjectRoot, 'app/src/main/java', ...paket.split('.'));
    fs.mkdirSync(klasor, { recursive: true });
    fs.writeFileSync(path.join(klasor, 'UyandirmaServisi.kt'), SERVIS(paket));
    fs.writeFileSync(path.join(klasor, 'UyandirmaActivity.kt'), ACTIVITY(paket));
    return c;
  }]);
  config = withAppBuildGradle(config, (c) => {
    if (!c.modResults.contents.includes('vosk-android')) {
      c.modResults.contents = c.modResults.contents.replace(/dependencies\s*\{/, `dependencies {
    implementation 'com.alphacephei:vosk-android:0.3.47'
    implementation 'net.java.dev.jna:jna:5.13.0@aar'`);
    }
    return c;
  });
  return withAndroidManifest(config, (c) => {
    const m = c.modResults.manifest;
    m['uses-permission'] = m['uses-permission'] || [];
    for (const izin of ['android.permission.FOREGROUND_SERVICE', 'android.permission.FOREGROUND_SERVICE_MICROPHONE',
      'android.permission.SYSTEM_ALERT_WINDOW', 'android.permission.RECORD_AUDIO']) {
      if (!m['uses-permission'].some((x) => x.$['android:name'] === izin)) m['uses-permission'].push({ $: { 'android:name': izin } });
    }
    const app = m.application[0];
    app.service = app.service || [];
    if (!app.service.some((s) => s.$['android:name'] === '.UyandirmaServisi')) {
      app.service.push({ $: { 'android:name': '.UyandirmaServisi', 'android:exported': 'false', 'android:foregroundServiceType': 'microphone' } });
    }
    if (!app.activity.some((a) => a.$['android:name'] === '.UyandirmaActivity')) {
      app.activity.push({ $: { 'android:name': '.UyandirmaActivity', 'android:exported': 'false', 'android:excludeFromRecents': 'true',
        'android:theme': '@android:style/Theme.Translucent.NoTitleBar', 'android:noHistory': 'true' } });
    }
    return c;
  });
};
