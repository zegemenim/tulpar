// Cihazlarım: hedef cihazı seç (Mac, telefon...), ses/müzik/parlaklık/rahatsız etme komutlarını düğmeyle gönder.
import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import * as IntentLauncher from 'expo-intent-launcher';
import { istek } from '../../lib/api';
import { useRenk } from '../../lib/tema';

const KOMUTLAR: { baslik: string; islemler: [string, string][] }[] = [
  { baslik: 'Ses', islemler: [['Aç', 'ses_ac'], ['Kıs', 'ses_kis'], ['Sessiz', 'sessiz']] },
  { baslik: 'Müzik', islemler: [['Devam / Oynat', 'medya_devam'], ['Duraklat', 'medya_dur'], ['Sonraki', 'medya_sonraki'], ['Önceki', 'medya_onceki']] },
  { baslik: 'Ekran', islemler: [['Parlaklık +', 'parlaklik_ac'], ['Parlaklık -', 'parlaklik_kis'], ['Rahatsız etme aç', 'rahatsiz_etme_ac'], ['Rahatsız etme kapat', 'rahatsiz_etme_kapat']] },
];

export default function Cihazlar() {
  const r = useRenk();
  const [cihazlar, setCihazlar] = useState<string[]>(['telefon', 'mac']);
  const [hedef, setHedef] = useState('mac');
  const [durum, setDurum] = useState('');
  const [sarki, setSarki] = useState('');

  useFocusEffect(useCallback(() => {
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
      <Text style={{ color: r.soluk, marginTop: 12 }}>Bu telefonun izinleri (bir kez ver)</Text>
      <View style={s.satir}>
        <Pressable onPress={() => ayar('android.settings.action.MANAGE_WRITE_SETTINGS', 'package:dev.tulpar.app')} style={[s.dugme, { backgroundColor: r.kart, borderColor: r.cizgi }]}>
          <Text style={{ color: r.yazi }}>Parlaklık izni</Text>
        </Pressable>
        <Pressable onPress={() => ayar('android.settings.NOTIFICATION_POLICY_ACCESS_SETTINGS')} style={[s.dugme, { backgroundColor: r.kart, borderColor: r.cizgi }]}>
          <Text style={{ color: r.yazi }}>Rahatsız etme izni</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  satir: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  dugme: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, borderWidth: StyleSheet.hairlineWidth },
  girdi: { flex: 1, minWidth: 160, paddingHorizontal: 12, borderRadius: 10, borderWidth: StyleSheet.hairlineWidth },
});
