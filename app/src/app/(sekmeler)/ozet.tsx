// WhatsApp özeti: son 24 saatte hangi sohbette ne konuşuldu; cevap bekleyenler üstte. Hazırlanması dakikalar sürebilir.
import { useCallback, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { istek, saat } from '../../lib/api';
import { useRenk } from '../../lib/tema';

type Ozet = { zaman: number; hazirlaniyor?: boolean; toplam?: number; sohbetler: { ad: string; grup: boolean; mesaj: number; ozet: string; cevap_gerekli: boolean; ne: string | null }[] };

export default function OzetEkrani() {
  const r = useRenk();
  const [o, setO] = useState<Ozet | null>(null);
  const [yuk, setYuk] = useState(false);
  const yenile = useCallback(async () => {
    setYuk(true);
    try { setO(await istek<Ozet>('/ozet', undefined, 8000)); } catch {} finally { setYuk(false); }
  }, []);
  useFocusEffect(useCallback(() => {
    yenile();
    const t = setInterval(yenile, 15000);  // hazırlanırken ilerlemeyi göster
    return () => clearInterval(t);
  }, [yenile]));
  const baslat = async () => { try { await istek('/ozet/yenile', {}, 8000); } catch {} yenile(); };

  return (
    <ScrollView style={{ backgroundColor: r.zemin }} contentContainerStyle={{ padding: 16, gap: 10 }}
      refreshControl={<RefreshControl refreshing={yuk} onRefresh={yenile} />}>
      <Pressable onPress={baslat} style={{ backgroundColor: r.ana, padding: 12, borderRadius: 10 }}>
        <Text style={{ color: r.anaYazi, fontWeight: '600', textAlign: 'center' }}>{o?.hazirlaniyor ? 'Hazırlanıyor…' : 'Özeti yenile (son 24 saat)'}</Text>
      </Pressable>
      {o?.zaman ? <Text style={{ color: r.soluk }}>Hazırlanma: {saat(o.zaman)}{o.hazirlaniyor ? ` · ${o.sohbetler.length}/${o.toplam ?? '?'} sohbet` : ''}</Text>
        : <Text style={{ color: r.soluk }}>Henüz özet yok.</Text>}
      {o?.sohbetler.map((s, i) => (
        <View key={i} style={{ backgroundColor: r.kart, borderRadius: 10, padding: 12, borderLeftWidth: 4, borderLeftColor: s.cevap_gerekli ? r.sari : r.cizgi }}>
          <Text style={{ color: r.yazi, fontWeight: '600' }}>{s.cevap_gerekli ? '⚠ ' : ''}{s.ad}{s.grup ? ' (grup)' : ''} · {s.mesaj} mesaj</Text>
          <Text style={{ color: r.yazi, marginTop: 4 }}>{s.ozet}</Text>
          {!!s.ne && <Text style={{ color: r.sari, marginTop: 4 }}>Senden beklenen: {s.ne}</Text>}
        </View>
      ))}
    </ScrollView>
  );
}
