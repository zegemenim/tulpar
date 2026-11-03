// Cihazlarım: hedef cihazı seç (Mac, telefon...), ses/müzik/parlaklık/rahatsız etme komutlarını düğmeyle gönder.
import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import * as IntentLauncher from 'expo-intent-launcher';
import * as Pano from 'expo-clipboard';
import { istek } from '../../lib/api';
import { useRenk } from '../../lib/tema';

const KOMUTLAR: { baslik: string; islemler: [string, string][] }[] = [
  { baslik: 'Ses', islemler: [['Aç', 'ses_ac'], ['Kıs', 'ses_kis'], ['Sessiz', 'sessiz']] },
  { baslik: 'Müzik kaynağı (Mac)', islemler: [['Sistem (en son çalan)', 'muzik_sistem'], ['Google Chrome', 'muzik_chrome']] },
  { baslik: 'Müzik', islemler: [['⏮ Önceki', 'medya_onceki'], ['⏯ Oynat / Duraklat', 'medya_cal'], ['⏭ Sonraki', 'medya_sonraki']] },
  { baslik: 'Ekran', islemler: [['Parlaklık +', 'parlaklik_ac'], ['Parlaklık -', 'parlaklik_kis'], ['Rahatsız etme aç', 'rahatsiz_etme_ac'], ['Rahatsız etme kapat', 'rahatsiz_etme_kapat']] },
];

export default function Cihazlar() {
  const r = useRenk();
  const [cihazlar, setCihazlar] = useState<string[]>(['telefon', 'mac']);
  const [hedef, setHedef] = useState('mac');
  const [durum, setDurum] = useState('');
  const [sarki, setSarki] = useState('');
  const [gecmis, setGecmis] = useState<{ metin: string; kaynak: string; zaman: number }[]>([]);

  useFocusEffect(useCallback(() => {
    istek<typeof gecmis>('/pano/gecmis?n=30', undefined, 8000).then(setGecmis).catch(() => {});
    istek<string[]>('/cihaz/liste', undefined, 8000).then((l) => l.length && setCihazlar(l)).catch(() => {});
  }, []));

  const gonder = async (islem: string, deger?: string) => {
    setDurum('gönderiliyor…');
    try { setDurum((await istek<{ durum: string }>('/cihaz/komut', { hedef, islem, deger }, 30000)).durum); }
    catch { setDurum('sunucuya ulaşılamadı'); }
  };
  const ayar = (eylem: string, veri?: string) => IntentLauncher.startActivityAsync(eylem, veri ? { data: veri } : undefined).catch(() => {});

  return (
    <ScrollView style={{ backgroundColor: r.zemin }} contentContainerStyle={{ padding: 16, gap: 14 }}>
      <Text style={{ color: r.soluk }}>Hedef cihaz</Text>
      <View style={s.satir}>
        {cihazlar.map((c) => (
          <Pressable key={c} onPress={() => setHedef(c)} style={[s.dugme, { backgroundColor: hedef === c ? r.ana : r.kart, borderColor: r.cizgi }]}>
            <Text style={{ color: hedef === c ? r.anaYazi : r.yazi, fontWeight: '600' }}>{c}</Text>
          </Pressable>
        ))}
      </View>
      {KOMUTLAR.map((g) => (
        <View key={g.baslik} style={{ gap: 8 }}>
          <Text style={{ color: r.soluk }}>{g.baslik}</Text>
          <View style={s.satir}>
            {g.islemler.map(([ad, islem]) => (
              <Pressable key={islem} onPress={() => gonder(islem)} style={[s.dugme, { backgroundColor: r.kart, borderColor: r.cizgi }]}>
                <Text style={{ color: r.yazi }}>{ad}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ))}
      <Text style={{ color: r.soluk }}>Şarkı çal (YouTube Music)</Text>
      <View style={s.satir}>
        <TextInput value={sarki} onChangeText={setSarki} placeholder="şarkı veya sanatçı" placeholderTextColor={r.soluk}
          style={[s.girdi, { color: r.yazi, backgroundColor: r.kart, borderColor: r.cizgi }]} />
        <Pressable onPress={() => sarki.trim() && gonder('sarki_cal', sarki.trim())} style={[s.dugme, { backgroundColor: r.ana, borderColor: r.ana }]}>
          <Text style={{ color: r.anaYazi, fontWeight: '600' }}>Çal</Text>
        </Pressable>
      </View>
      {!!durum && <Text style={{ color: r.soluk }}>Durum: {durum}</Text>}
      <Text style={{ color: r.soluk, marginTop: 12 }}>Pano geçmişi (7 gün, dokununca kopyalanır)</Text>
      {gecmis.length === 0 && <Text style={{ color: r.soluk }}>(boş)</Text>}
      {gecmis.map((g) => (
        <Pressable key={g.zaman} onPress={() => Pano.setStringAsync(g.metin)} style={[s.dugme, { backgroundColor: r.kart, borderColor: r.cizgi }]}>
          <Text numberOfLines={2} style={{ color: r.yazi }}>{g.metin}</Text>
          <Text style={{ color: r.soluk, fontSize: 11 }}>{g.kaynak} · {new Date(g.zaman * 1000).toLocaleString('tr-TR')}</Text>
        </Pressable>
      ))}
      <Text style={{ color: r.soluk, marginTop: 12 }}>Bu telefonun izinleri (bir kez ver)</Text>
      <View style={s.satir}>
        <Pressable onPress={() => ayar('android.settings.action.MANAGE_WRITE_SETTINGS', 'package:dev.tulpar.app')} style={[s.dugme, { backgroundColor: r.kart, borderColor: r.cizgi }]}>
          <Text style={{ color: r.yazi }}>Parlaklık izni</Text>
        </Pressable>
        <Pressable onPress={() => ayar('android.settings.NOTIFICATION_POLICY_ACCESS_SETTINGS')} style={[s.dugme, { backgroundColor: r.kart, borderColor: r.cizgi }]}>
          <Text style={{ color: r.yazi }}>Rahatsız etme izni</Text>
        </Pressable>
      </View>
      <Pressable onPress={() => ayar('android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS')} style={[s.dugme, { backgroundColor: r.kart, borderColor: r.cizgi, alignSelf: 'flex-start', marginBottom: 8 }]}>
        <Text style={{ color: r.yazi }}>Bildirim erişimi (bildirimleri Tulpar okusun)</Text>
      </Pressable>
      <Pressable onPress={() => ayar('android.settings.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS', 'package:dev.tulpar.app')} style={[s.dugme, { backgroundColor: r.kart, borderColor: r.cizgi, alignSelf: 'flex-start' }]}>
        <Text style={{ color: r.yazi }}>Pil kısıtını kaldır (komutlar arka planda çalışsın)</Text>
      </Pressable>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  satir: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  dugme: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, borderWidth: StyleSheet.hairlineWidth },
  girdi: { flex: 1, minWidth: 160, paddingHorizontal: 12, borderRadius: 10, borderWidth: StyleSheet.hairlineWidth },
});
