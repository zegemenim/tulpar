// Telefonu uzaktan kontrol: HP'nin /cihaz/bekleyen/telefon sırasındaki komutları (ses, parlaklık, rahatsız etme, müzik)
// uygular. Komut döngüsü UyandirmaServisi içinden başlar (servis zaten sürekli çalışıyor). Parlaklık ve rahatsız etme için
// kullanıcının bir kez "Cihazlarım" ekranından izin vermesi gerekir.
const fs = require('fs');
const path = require('path');
const { withAndroidManifest, withDangerousMod, withMainActivity } = require('expo/config-plugins');

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

const SERVIS = (p) => `package ${p}

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

// Uygulama açılınca (ön plandayken) başlar ve komut sırasını sürekli dinler. Ayrı servis: uyandırma servisi arka planda
// yeniden başlatılamadığı için (Android mikrofon servisine izin vermiyor) komutlar ona bağlı olamaz.
class CihazServisi : Service() {
  override fun onBind(i: Intent?): IBinder? = null

  override fun onStartCommand(i: Intent?, f: Int, id: Int): Int {
    val nm = getSystemService(NotificationManager::class.java)
    nm.createNotificationChannel(NotificationChannel("cihaz", "Cihaz komutları", NotificationManager.IMPORTANCE_MIN))
    val n = Notification.Builder(this, "cihaz").setSmallIcon(android.R.drawable.ic_menu_manage)
      .setContentTitle("Tulpar cihaz kontrolü").setContentText("Bilgisayardan gelen komutlar dinleniyor").build()
    if (Build.VERSION.SDK_INT >= 34) startForeground(43, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE) else startForeground(43, n)
    CihazKomutu.baslat(this)
    return START_STICKY
  }
}
`;

const DINLEYICI = (p) => `package ${p}

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

// Telefona gelen bildirimleri (banka SMS'i, kargo, uygulama uyarıları) HP'ye iletir. Kullanıcı bir kez "Bildirim erişimi" verir.
// WhatsApp zaten köprüden geliyor, kalıcı/ilerleme bildirimleri anlamsız: ikisi de atlanır. Doğrulama kodlarını sunucu süzer.
class BildirimDinleyici : NotificationListenerService() {
  companion object {
    private val tampon = ArrayList<JSONObject>()
    @Volatile private var gonderici = false
    private val ATLA = setOf("com.whatsapp", "com.whatsapp.w4b", "dev.tulpar.app", "android", "com.android.systemui")
  }

  override fun onNotificationPosted(sbn: StatusBarNotification) {
    val n = sbn.notification
    if (sbn.packageName in ATLA || sbn.isOngoing || (n.flags and Notification.FLAG_GROUP_SUMMARY) != 0) return
    if (n.category == Notification.CATEGORY_TRANSPORT || n.category == Notification.CATEGORY_PROGRESS || n.category == Notification.CATEGORY_CALL) return
    val e = n.extras
    val baslik = e.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
    val metin = (e.getCharSequence(Notification.EXTRA_BIG_TEXT) ?: e.getCharSequence(Notification.EXTRA_TEXT))?.toString() ?: ""
    if (baslik.isBlank() && metin.isBlank()) return
    val pk = sbn.packageName
    val tur = if (pk.contains("sms") || pk.contains("mms") || pk.contains("messaging")) "sms" else "bildirim"
    synchronized(tampon) {
      if (tampon.size >= 500) tampon.removeAt(0)
      tampon.add(JSONObject().put("paket", sbn.packageName).put("baslik", baslik).put("metin", metin).put("tur", tur).put("zaman", sbn.postTime / 1000.0))
    }
    baslat()
  }

  private fun baslat() {
    if (gonderici) return
    gonderici = true
    val ctx = applicationContext
    Thread {
      while (true) {
        Thread.sleep(15000)
        try { gonder(ctx) } catch (e: Exception) { Log.w("Tulpar", "bildirim gönderilemedi: " + e.message) }
      }
    }.start()
  }

  private fun gonder(ctx: android.content.Context) {
    val paket = synchronized(tampon) { if (tampon.isEmpty()) return; ArrayList(tampon) }
    val ayar = File(ctx.filesDir, "sunucu.json")
    if (!ayar.exists()) return
    val j = JSONObject(ayar.readText())
    val adresler = j.getJSONArray("adresler")
    val govde = JSONObject().put("liste", JSONArray(paket)).toString().toByteArray()
    for (i in 0 until adresler.length()) {
      try {
        val b = URL(adresler.getString(i).trimEnd('/') + "/bildirim").openConnection() as HttpURLConnection
        b.connectTimeout = 3000; b.readTimeout = 5000; b.requestMethod = "POST"; b.doOutput = true
        b.setRequestProperty("x-tulpar-anahtar", j.getString("anahtar")); b.setRequestProperty("Content-Type", "application/json")
        b.outputStream.use { it.write(govde) }
        if (b.responseCode != 200) continue
        synchronized(tampon) { tampon.removeAll(paket.toSet()) }  // gönderilenler çıkar, bu arada gelenler kalır
        return
      } catch (e: Exception) { continue }
    }
  }
}
`;

const ALICI = (p) => `package ${p}

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

// Telefon açılınca ve uygulama güncellenince komut servisini yeniden başlatır (uygulamayı elle açmak gerekmesin).
class CihazAlici : BroadcastReceiver() {
  override fun onReceive(c: Context, i: Intent) {
    try { c.startForegroundService(Intent(c, CihazServisi::class.java)) } catch (e: Exception) { Log.w("Tulpar", "cihaz servisi başlatılamadı: " + e.message) }
  }
}
`;

module.exports = function cihaz(config) {
  const paket = config.android.package;
  config = withDangerousMod(config, ['android', async (c) => {
    const klasor = path.join(c.modRequest.platformProjectRoot, 'app/src/main/java', ...paket.split('.'));
    fs.mkdirSync(klasor, { recursive: true });
    fs.writeFileSync(path.join(klasor, 'CihazKomutu.kt'), KOTLIN(paket));
    fs.writeFileSync(path.join(klasor, 'CihazServisi.kt'), SERVIS(paket));
    fs.writeFileSync(path.join(klasor, 'CihazAlici.kt'), ALICI(paket));
    fs.writeFileSync(path.join(klasor, 'BildirimDinleyici.kt'), DINLEYICI(paket));
    return c;
  }]);
  config = withMainActivity(config, (c) => {
    const kod = 'startForegroundService(android.content.Intent(this, CihazServisi::class.java))';
    if (!c.modResults.contents.includes('CihazServisi')) {
      c.modResults.contents = c.modResults.contents.replace(/(super\.onCreate\([^)]*\)\n)/, `$1    ${kod}\n`);
    }
    return c;
  });
  return withAndroidManifest(config, (c) => {
    const m = c.modResults.manifest;
    m['uses-permission'] = m['uses-permission'] || [];
    for (const izin of ['android.permission.RECEIVE_BOOT_COMPLETED', 'android.permission.FOREGROUND_SERVICE', 'android.permission.FOREGROUND_SERVICE_SPECIAL_USE', 'android.permission.MODIFY_AUDIO_SETTINGS', 'android.permission.WRITE_SETTINGS', 'android.permission.ACCESS_NOTIFICATION_POLICY']) {
      if (!m['uses-permission'].some((x) => x.$['android:name'] === izin)) m['uses-permission'].push({ $: { 'android:name': izin } });
    }
    const app = m.application[0];
    app.service = app.service || [];
    if (!app.service.some((x) => x.$['android:name'] === '.CihazServisi')) {
      app.service.push({ $: { 'android:name': '.CihazServisi', 'android:exported': 'false', 'android:foregroundServiceType': 'specialUse' },
        property: [{ $: { 'android:name': 'android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE', 'android:value': 'remote_device_control' } }] });
    }
    if (!app.service.some((x) => x.$['android:name'] === '.BildirimDinleyici')) {
      app.service.push({ $: { 'android:name': '.BildirimDinleyici', 'android:exported': 'true', 'android:label': 'Tulpar bildirim okuma', 'android:permission': 'android.permission.BIND_NOTIFICATION_LISTENER_SERVICE' },
        'intent-filter': [{ action: [{ $: { 'android:name': 'android.service.notification.NotificationListenerService' } }] }] });
    }
    app.receiver = app.receiver || [];
    if (!app.receiver.some((x) => x.$['android:name'] === '.CihazAlici')) {
      app.receiver.push({ $: { 'android:name': '.CihazAlici', 'android:exported': 'true' },
        'intent-filter': [{ action: [{ $: { 'android:name': 'android.intent.action.BOOT_COMPLETED' } }, { $: { 'android:name': 'android.intent.action.MY_PACKAGE_REPLACED' } }] }] });
    }
    return c;
  });
};
