// Görevler: yazarak veya sesle ekle, dokununca bitir. Sesle eklemede Tulpar tarihi/saati kendisi çıkarır.
import { useCallback, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Gorev, istek } from '../../lib/api';
import { durumYazisi, useSesliAsistan } from '../../lib/ses';
import { useRenk } from '../../lib/tema';

export default function Gorevler() {
  const r = useRenk();
  const [acik, setAcik] = useState<Gorev[]>([]);
  const [biten, setBiten] = useState<Gorev[]>([]);
  const [yazi, setYazi] = useState('');
  const [yuk, setYuk] = useState(false);
  const [son, setSon] = useState<string | null>(null);

  const yenile = useCallback(async () => {
    setYuk(true);
    try {
      setAcik(await istek<Gorev[]>('/gorevler?durum=acik'));
      setBiten((await istek<Gorev[]>('/gorevler?durum=bitti')).slice(0, 15));
    } catch {} finally { setYuk(false); }
  }, []);
  useFocusEffect(useCallback(() => { yenile(); }, [yenile]));

  // Sesli/yazılı ekleme Tulpar üzerinden: "yarın 3'te dişçi" -> tarih ve saatli görev
  const asistan = useSesliAsistan(useCallback((k) => { if (k.kim === 'tulpar') { setSon(k.metin); yenile(); } }, [yenile]));
  const ekle = () => {
    const m = yazi.trim();
    if (!m) return;
    setYazi('');
    asistan.sor(`Görev ekle: ${m}`, false);
  };
  const degistir = async (g: Gorev) => {
    await istek(`/gorev/${g.id}`, { durum: g.durum === 'acik' ? 'bitti' : 'acik' });
    yenile();
  };

  const satir = (g: Gorev) => (
    <Pressable key={g.id} onPress={() => degistir(g)} style={[s.satir, { backgroundColor: r.kart, borderColor: r.cizgi }]}>
      <Ionicons name={g.durum === 'acik' ? 'square-outline' : 'checkbox'} size={22} color={g.durum === 'acik' ? r.soluk : r.yesil} />
      <View style={{ flex: 1 }}>
        <Text style={{ color: r.yazi, textDecorationLine: g.durum === 'bitti' ? 'line-through' : 'none' }}>{g.metin}</Text>
        {g.zaman ? <Text style={{ color: r.ana, fontSize: 12 }}>{g.zaman}</Text> : null}
      </View>
    </Pressable>
  );

  const dinliyor = asistan.durum === 'dinliyor';
  return (
    <View style={{ flex: 1, backgroundColor: r.zemin }}>
      <View style={[s.ekle, { backgroundColor: r.kart, borderBottomColor: r.cizgi }]}>
        <TextInput value={yazi} onChangeText={setYazi} onSubmitEditing={ekle} returnKeyType="done"
          placeholder="Görev ekle: yarın 15:00 dişçi" placeholderTextColor={r.soluk}
          style={[s.girdi, { color: r.yazi, backgroundColor: r.zemin, borderColor: r.cizgi }]} />
        <Pressable onPress={() => (dinliyor ? asistan.bitir() : asistan.basla())} style={[s.mik, { backgroundColor: dinliyor ? r.kirmizi : r.ana }]}>
          <Ionicons name={dinliyor ? 'stop' : 'mic'} size={22} color="#fff" />
        </Pressable>
      </View>
      {asistan.durum !== 'bos' && <Text style={{ color: r.soluk, padding: 8, textAlign: 'center' }}>{durumYazisi[asistan.durum]}</Text>}
      {son && <Text style={{ color: r.soluk, paddingHorizontal: 12, paddingTop: 8 }}>Tulpar: {son}</Text>}
      <ScrollView contentContainerStyle={{ padding: 12 }} refreshControl={<RefreshControl refreshing={yuk} onRefresh={yenile} />}>
        {acik.length ? acik.map(satir) : <Text style={{ color: r.soluk }}>Açık görev yok.</Text>}
        {biten.length > 0 && <Text style={[s.bolum, { color: r.soluk }]}>BİTENLER</Text>}
        {biten.map(satir)}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  ekle: { flexDirection: 'row', gap: 8, padding: 10, borderBottomWidth: StyleSheet.hairlineWidth, alignItems: 'center' },
  girdi: { flex: 1, borderWidth: 1, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  mik: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  satir: { flexDirection: 'row', gap: 10, alignItems: 'center', borderWidth: 1, borderRadius: 10, padding: 12, marginBottom: 6 },
  bolum: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5, marginTop: 14, marginBottom: 6 },
});
