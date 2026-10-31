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
import org.json.JSONArray
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.SpeakerModel
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import java.io.File
import java.io.InputStream
import java.net.URL
import java.util.zip.ZipInputStream
import kotlin.math.sqrt

class UyandirmaServisi : Service(), RecognitionListener {
  private var konusma: SpeechService? = null
  private var model: Model? = null
  private var spkModel: SpeakerModel? = null
  private val ana = Handler(Looper.getMainLooper())
  private val kelime = Regex("\\\\b(tulpar|tul par|tülpar|kahya|kâhya|kah ya)\\\\b", RegexOption.IGNORE_CASE)

  // "Sesimi öğren" ile öğrenilen kişisel varyantlar ve ses parmak izi
  private val varyantDosya get() = File(filesDir, "uyandirma_varyant.txt")
  private val ogrenilenDosya get() = File(filesDir, "uyandirma_ogrenilen.txt")
  private val sesDosya get() = File(filesDir, "uyandirma_ses.txt")            // ortalama ses vektörü
  private val yalnizDosya get() = File(filesDir, "uyandirma_yalniz_ben.txt")  // varsa: sadece benim sesimle
  private var varyantlar: List<String> = emptyList()
  private var benimSes: DoubleArray? = null
  private var yalnizBen = false
  private var ogreniyor = false
  private val ogrenilen = linkedSetOf<String>()
  private val ogrenilenSes = mutableListOf<DoubleArray>()
  private val ESIK = 0.55  // kosinüs uzaklığı bundan küçükse "aynı kişi"

  override fun onBind(intent: Intent?): IBinder? = null

  private fun varyantYukle() {
    varyantlar = if (varyantDosya.exists()) varyantDosya.readLines().map { it.trim().lowercase() }.filter { it.length >= 3 } else emptyList()
    val ses = if (sesDosya.exists()) sesDosya.readText().trim().split(",").mapNotNull { it.toDoubleOrNull() } else emptyList()
    benimSes = if (ses.isNotEmpty()) ses.toDoubleArray() else null
    yalnizBen = yalnizDosya.exists() && benimSes != null
  }

  private fun eslesir(metin: String): Boolean {
    if (kelime.containsMatchIn(metin)) return true
    val t = " " + metin.lowercase() + " "
    return varyantlar.any { t.contains(" " + it + " ") }
  }

  private fun vektor(a: JSONArray): DoubleArray = DoubleArray(a.length()) { a.getDouble(it) }

  private fun uzaklik(a: DoubleArray, b: DoubleArray): Double {
    var ab = 0.0; var aa = 0.0; var bb = 0.0
    for (i in a.indices) { ab += a[i] * b[i]; aa += a[i] * a[i]; bb += b[i] * b[i] }
    return 1.0 - ab / (sqrt(aa) * sqrt(bb) + 1e-9)
  }

  override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    when (intent?.getStringExtra("ogren")) {
      "basla" -> { ogrenilen.clear(); ogrenilenSes.clear(); ogrenilenDosya.writeText(""); ogreniyor = true }
      "bitir" -> {
        ogreniyor = false
        if (ogrenilenSes.size >= 3) {  // ses parmak izi: duyulan cümlelerin ortalaması
          val n = ogrenilenSes[0].size
          val ort = DoubleArray(n) { i -> ogrenilenSes.sumOf { it[i] } / ogrenilenSes.size }
          sesDosya.writeText(ort.joinToString(","))
        }
        val eski = if (varyantDosya.exists()) varyantDosya.readLines() else emptyList()
        varyantDosya.writeText((eski + ogrenilen).map { it.trim().lowercase() }
          .filter { it.length >= 3 && !kelime.containsMatchIn(it) }.distinct().joinToString("\\n"))
        varyantYukle()
      }
      "yukle" -> varyantYukle()
      "duraklat" -> { durdur(); ana.postDelayed({ dinle() }, 45000) }  // güç tuşuyla açıldı: mikrofonu uygulamaya bırak
    }
    return START_STICKY
  }

  override fun onCreate() {
    super.onCreate()
    bildirim("Ses modeli hazırlanıyor…")
    File(filesDir, "uyandirma_acik").writeText("1")  // yeniden başlatma/güncelleme sonrası hatırlatmak için
    varyantYukle()
    Thread { hazirla() }.start()
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

  private fun zipAc(kaynak: InputStream) {
    ZipInputStream(kaynak).use { zip ->
      var g = zip.nextEntry
      while (g != null) {
        val hedef = File(filesDir, g.name)
        if (!hedef.canonicalPath.startsWith(filesDir.canonicalPath)) throw SecurityException("zip yolu")
        if (g.isDirectory) hedef.mkdirs() else { hedef.parentFile?.mkdirs(); hedef.outputStream().use { zip.copyTo(it) } }
        g = zip.nextEntry
      }
    }
  }

  private fun hazirla() {
    try {
      val klasor = File(filesDir, "${MODEL_KLASOR}")
      if (!File(klasor, "conf").exists()) {
        ana.post { bildirim("Türkçe ses modeli hazırlanıyor (37 MB, bir kez)…") }
        // önce uygulamanın HP'den indirdiği kopya (files/vosk-tr.zip), yoksa internetten
        val yerel = File(filesDir, "vosk-tr.zip")
        try {
          zipAc(if (yerel.exists()) yerel.inputStream() else URL("${MODEL_URL}").openStream())
        } catch (e: Exception) {  // bozuk/yarım zip: silinir ki bir sonraki denemede baştan inebilsin
          yerel.delete(); klasor.deleteRecursively(); throw e
        }
        yerel.delete()
      }
      model = Model(klasor.absolutePath)
      try {  // konuşmacı modeli (13 MB): yoksa sorun değil, sadece "sadece benim sesimle" çalışmaz
        val spk = File(filesDir, "vosk-model-spk-0.4")
        if (!spk.exists() || spk.list()?.isEmpty() != false) {
          val yerelSpk = File(filesDir, "vosk-spk.zip")
          if (yerelSpk.exists()) {
            try { zipAc(yerelSpk.inputStream()) } catch (e: Exception) { yerelSpk.delete(); spk.deleteRecursively(); throw e }
            yerelSpk.delete()
          }
        }
        if (spk.exists()) spkModel = SpeakerModel(spk.absolutePath)
      } catch (e: Exception) { Log.e("Tulpar", "konusmaci modeli", e) }
      ana.post { dinle() }
    } catch (e: Exception) {
      Log.e("Tulpar", "uyandirma modeli", e)
      ana.post { bildirim("Ses modeli hazırlanamadı: " + e.message) }
    }
  }

  private fun dinle() {
    val m = model ?: return
    if (konusma != null) return
    try {
      val tanima = spkModel?.let { Recognizer(m, 16000f, it) } ?: Recognizer(m, 16000f)
      konusma = SpeechService(tanima, 16000f).also { it.startListening(this) }
      bildirim("“Tulpar” ya da “Kâhya” de")
    } catch (e: Exception) {
      Log.e("Tulpar", "dinleme baslamadi", e)
      ana.postDelayed({ dinle() }, 10000)  // mikrofon başka uygulamadaysa sonra tekrar dene
    }
  }

  private fun durdur() { konusma?.stop(); konusma?.shutdown(); konusma = null }

  private fun kontrol(hipotez: String?, son: Boolean) {
    if (hipotez == null || konusma == null) return
    val j = JSONObject(hipotez)
    val metin = if (son) j.optString("text", "") else j.optString("partial", "")
    if (ogreniyor) {  // öğrenme: duyulanları topla (uyandırma tetiklenmez)
      if (son) {
        metin.split(" ").map { it.trim().lowercase() }.filter { it.length >= 3 }.forEach { ogrenilen.add(it) }
        ogrenilenDosya.writeText(ogrenilen.joinToString("\\n"))
        val spk = j.optJSONArray("spk")
        if (spk != null && j.optInt("spk_frames", 0) >= 20 && metin.isNotBlank()) ogrenilenSes.add(vektor(spk))
      }
      return
    }
    if (!eslesir(metin)) return
    if (yalnizBen) {  // ses parmak izi sadece cümle bitince hesaplanır
      if (!son) return
      val spk = j.optJSONArray("spk") ?: return
      if (j.optInt("spk_frames", 0) < 15) return
      val d = uzaklik(benimSes!!, vektor(spk))
      Log.i("Tulpar", "uyandirma ses uzakligi: " + d)
      if (d > ESIK) return  // başka biri
    }
    durdur()  // mikrofonu uygulamaya bırak
    startActivity(Intent(this, AsistanActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    ana.postDelayed({ dinle() }, 45000)
  }

  override fun onPartialResult(h: String?) = kontrol(h, false)
  override fun onResult(h: String?) = kontrol(h, true)
  override fun onFinalResult(h: String?) = kontrol(h, true)
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
    val islem = intent.getStringExtra("islem")
    if (islem == "kapat") {
      java.io.File(filesDir, "uyandirma_acik").delete()
      stopService(servis)
    } else if (islem == "ogren_basla" || islem == "ogren_bitir" || islem == "yukle") {
      startForegroundService(servis.putExtra("ogren", islem.removePrefix("ogren_")))
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

const ALICI = (p) => `package ${p}

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import java.io.File

// Telefon yeniden açılınca veya uygulama güncellenince uyandırma servisi durur. Android, arka plandan mikrofon servisi
// başlatmaya izin vermiyor; bu yüzden tek dokunuşluk bir bildirim gösterir (ve uygulama açılınca servis kendiliğinden başlar).
class UyandirmaAlici : BroadcastReceiver() {
  override fun onReceive(c: Context, i: Intent) {
    if (!File(c.filesDir, "uyandirma_acik").exists()) return
    val nm = c.getSystemService(NotificationManager::class.java)
    nm.createNotificationChannel(NotificationChannel("uyandirma_hatirlat", "Uyandırma hatırlatma", NotificationManager.IMPORTANCE_DEFAULT))
    val ac = PendingIntent.getActivity(c, 1, Intent(c, UyandirmaActivity::class.java).putExtra("islem", "ac"),
      PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    nm.notify(42, Notification.Builder(c, "uyandirma_hatirlat").setContentTitle("Tulpar uyandırma durdu")
      .setContentText("Yeniden başlatmak için dokun").setSmallIcon(android.R.drawable.ic_btn_speak_now)
      .setContentIntent(ac).setAutoCancel(true).build())
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
    fs.writeFileSync(path.join(klasor, 'UyandirmaAlici.kt'), ALICI(paket));
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
      'android.permission.SYSTEM_ALERT_WINDOW', 'android.permission.RECORD_AUDIO', 'android.permission.RECEIVE_BOOT_COMPLETED']) {
      if (!m['uses-permission'].some((x) => x.$['android:name'] === izin)) m['uses-permission'].push({ $: { 'android:name': izin } });
    }
    const app = m.application[0];
    app.service = app.service || [];
    if (!app.service.some((s) => s.$['android:name'] === '.UyandirmaServisi')) {
      app.service.push({ $: { 'android:name': '.UyandirmaServisi', 'android:exported': 'false', 'android:foregroundServiceType': 'microphone' } });
    }
    app.receiver = app.receiver || [];
    if (!app.receiver.some((r) => r.$['android:name'] === '.UyandirmaAlici')) {
      app.receiver.push({ $: { 'android:name': '.UyandirmaAlici', 'android:exported': 'true' },
        'intent-filter': [{ action: [{ $: { 'android:name': 'android.intent.action.BOOT_COMPLETED' } }, { $: { 'android:name': 'android.intent.action.MY_PACKAGE_REPLACED' } }] }] });
    }
    if (!app.activity.some((a) => a.$['android:name'] === '.UyandirmaActivity')) {
      app.activity.push({ $: { 'android:name': '.UyandirmaActivity', 'android:exported': 'false', 'android:excludeFromRecents': 'true',
        'android:theme': '@android:style/Theme.Translucent.NoTitleBar', 'android:noHistory': 'true' } });
    }
    return c;
  });
};
