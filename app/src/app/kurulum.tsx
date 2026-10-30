// İlk açılış: sunucu adresi (Tailscale) ve anahtar.
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { ayarYaz, istek } from '../lib/api';
import { bildirimleriBaslat } from '../lib/bildirim';
import { useRenk } from '../lib/tema';

export default function Kurulum() {
  const r = useRenk();
  const [adres, setAdres] = useState('http://');
  const [anahtar, setAnahtar] = useState('');
  const [deniyor, setDeniyor] = useState(false);

  const baglan = async () => {
    setDeniyor(true);
    try {
      await ayarYaz({ adres, anahtar });
      await istek('/durum', undefined, 15000);
      await bildirimleriBaslat().catch(() => {});
      router.replace('/');
    } catch (e: any) {
      Alert.alert('Bağlanamadı', `${e.message}\n\nTailscale açık mı, adres ve anahtar doğru mu?`);
    } finally {
      setDeniyor(false);
    }
  };

  const girdi = [s.girdi, { color: r.yazi, borderColor: r.cizgi, backgroundColor: r.kart }];
  return (
    <View style={[s.kap, { backgroundColor: r.zemin }]}>
      <Text style={[s.bas, { color: r.yazi }]}>Tulpar'a bağlan</Text>
      <Text style={{ color: r.soluk, marginBottom: 16 }}>
        Telefonda Tailscale açık olmalı. Adres örneği: http://100.x.y.z:8090. Anahtar sunucuda ~/tulpar/veri/anahtar dosyasında.
      </Text>
      <Text style={{ color: r.soluk }}>Sunucu adresi</Text>
      <TextInput value={adres} onChangeText={setAdres} autoCapitalize="none" keyboardType="url" style={girdi} />
      <Text style={{ color: r.soluk }}>Anahtar</Text>
      <TextInput value={anahtar} onChangeText={setAnahtar} autoCapitalize="none" secureTextEntry style={girdi} />
      <Pressable disabled={deniyor} onPress={baglan} style={[s.buton, { backgroundColor: r.ana, opacity: deniyor ? 0.5 : 1 }]}>
        <Text style={{ color: r.anaYazi, fontWeight: '700', fontSize: 16 }}>{deniyor ? 'Deneniyor…' : 'Bağlan'}</Text>
      </Pressable>
    </View>
  );
}

const s = StyleSheet.create({
  kap: { flex: 1, padding: 20 },
  bas: { fontSize: 24, fontWeight: '700', marginBottom: 8 },
  girdi: { borderWidth: 1, borderRadius: 10, padding: 12, marginTop: 4, marginBottom: 14, fontSize: 15 },
  buton: { borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 8 },
});
