// Ayarlar: sunucu bağlantısı, açılışta dinleme, reddedilen onaylar (7 gün saklanır), asistan kurulumu.
import { useCallback, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import * as SecureStore from 'expo-secure-store';
import OnayKart from '../../bilesenler/OnayKart';
import { denetle, indirVeKur, mevcutSurum } from '../../lib/guncelleme';
import { ayarOku, istek, Onay } from '../../lib/api';
import { useRenk } from '../../lib/tema';

export default function Ayarlar() {
  const r = useRenk();
  const [adres, setAdres] = useState('');
  const [dinle, setDinle] = useState(true);
  const [red, setRed] = useState<Onay[]>([]);
  const [durum, setDurum] = useState<string>('');

  const yenile = useCallback(async () => {
    setAdres((await ayarOku())?.adres ?? '');
    setDinle((await SecureStore.getItemAsync('acilista_dinle')) !== 'hayir');
    try {
      setRed(await istek<Onay[]>('/onaylar?durum=reddedildi'));
      const d = await istek<any>('/durum', undefined, 10000);
      setDurum(`Bağlı · ${d.mesaj_sayisi} mesaj · kuyrukta ${d.hizli_kuyruk} iş`);
    } catch (e: any) {
      setDurum(`Bağlantı yok: ${e.message}`);
    }
  }, []);
  useFocusEffect(useCallback(() => { yenile(); }, [yenile]));

  const kart = [s.kart, { backgroundColor: r.kart, borderColor: r.cizgi }];
  return (
    <ScrollView style={{ backgroundColor: r.zemin }} contentContainerStyle={{ padding: 14 }}>
      <View style={kart}>
        <Text style={[s.bas, { color: r.yazi }]}>Sunucu</Text>
        <Text style={{ color: r.soluk }}>{adres}</Text>
        <Text style={{ color: durum.startsWith('Bağlı') ? r.yesil : r.kirmizi, marginTop: 4 }}>{durum}</Text>
        <Pressable onPress={() => router.push('/kurulum')} style={{ marginTop: 8 }}>
          <Text style={{ color: r.ana, fontWeight: '600' }}>Adresi veya anahtarı değiştir</Text>
        </Pressable>
      </View>

      <View style={kart}>
        <Text style={[s.bas, { color: r.yazi }]}>Uygulama sürümü: {mevcutSurum()}</Text>
        <Pressable onPress={async () => {
          try {
            const y = await denetle();
            if (!y) return Alert.alert('Güncel', 'En son sürümü kullanıyorsun.');
            await indirVeKur();
          } catch (e: any) { Alert.alert('Güncellenemedi', e.message); }
        }}>
          <Text style={{ color: r.ana, fontWeight: '600', marginTop: 4 }}>Güncellemeleri denetle</Text>
        </Pressable>
      </View>

      <View style={[kart, s.satir]}>
        <View style={{ flex: 1 }}>
          <Text style={[s.bas, { color: r.yazi }]}>Asistan olarak açılınca dinle</Text>
          <Text style={{ color: r.soluk }}>Güç tuşuna basılı tutunca (veya sesle) açılınca hemen dinler. Uygulamayı kendin açınca dinlemez.</Text>
        </View>
        <Switch value={dinle} onValueChange={(v) => { setDinle(v); SecureStore.setItemAsync('acilista_dinle', v ? 'evet' : 'hayir'); }} />
      </View>

      <View style={kart}>
        <Text style={[s.bas, { color: r.yazi }]}>Asistan olarak kullan</Text>
        <Text style={{ color: r.soluk }}>
          Telefon Ayarları → Uygulamalar → Varsayılan uygulamalar → Dijital asistan uygulaması → Tulpar.{'\n'}
          Sonra güç veya ana ekran tuşuna basılı tutunca Tulpar açılır ve dinler.{'\n'}
          Bildirimlerin gelmesi için: Ayarlar → Pil → Tulpar → Kısıtlama yok.
        </Text>
      </View>

      <Text style={[s.bolum, { color: r.soluk }]}>REDDEDİLENLER (7 gün sonra silinir)</Text>
      {red.length ? red.map((o) => <OnayKart key={o.id} o={o} bitti={yenile} geriAl />)
        : <Text style={{ color: r.soluk }}>Reddedilen bir şey yok.</Text>}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  kart: { borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 12 },
  satir: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  bas: { fontSize: 16, fontWeight: '700', marginBottom: 4 },
  bolum: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5, marginTop: 6, marginBottom: 6 },
});
