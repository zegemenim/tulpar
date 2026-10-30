// Bir WhatsApp sohbeti: mesajlar WhatsApp gibi, alıntılar görünür; Tulpar'ın kararları ve bekleyen taslaklar altta.
import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect, useLocalSearchParams, useNavigation } from 'expo-router';
import TaslakKart from '../../bilesenler/TaslakKart';
import { istek, Mesaj, saat, Taslak } from '../../lib/api';
import { useRenk } from '../../lib/tema';

type Veri = { mesajlar: Mesaj[]; taslaklar: Taslak[]; mod: string | null };
const MODLAR = [['tam', 'TAM'], ['onemli', 'ÖNEMLİ'], ['kapali', 'KAPALI']] as const;

export default function SohbetEkrani() {
  const r = useRenk();
  const { id, ad } = useLocalSearchParams<{ id: string; ad?: string }>();
  const nav = useNavigation();
  const [veri, setVeri] = useState<Veri | null>(null);
  const liste = useRef<FlatList>(null);

  useLayoutEffect(() => { nav.setOptions({ title: ad || 'Sohbet' }); }, [nav, ad]);
  const yenile = useCallback(async () => {
    try { setVeri(await istek<Veri>(`/sohbet/${encodeURIComponent(id)}`)); } catch {}
  }, [id]);
  useFocusEffect(useCallback(() => { yenile(); }, [yenile]));

  const grup = id?.endsWith('@g.us');
  const mod = veri?.mod ?? (grup ? 'onemli' : 'tam');
  const modDegis = async (m: string) => { await istek(`/sohbet/${encodeURIComponent(id)}/mod`, { mod: m }); yenile(); };

  return (
    <View style={{ flex: 1, backgroundColor: r.zemin }}>
      <View style={[s.modlar, { backgroundColor: r.kart, borderBottomColor: r.cizgi }]}>
        <Text style={{ color: r.soluk, fontSize: 12 }}>Tulpar bu sohbette:</Text>
        {MODLAR.map(([k, e]) => (
          <Pressable key={k} onPress={() => modDegis(k)} style={[s.modCip, { borderColor: r.ana, backgroundColor: mod === k ? r.ana : 'transparent' }]}>
            <Text style={{ color: mod === k ? r.anaYazi : r.ana, fontSize: 12, fontWeight: '600' }}>{e}</Text>
          </Pressable>
        ))}
      </View>
      <FlatList ref={liste} data={veri?.mesajlar ?? []} keyExtractor={(m) => m.id}
        onContentSizeChange={() => liste.current?.scrollToEnd({ animated: false })}
        contentContainerStyle={{ padding: 10 }}
        renderItem={({ item: m }) => {
          const ben = !!m.benden;
          const e = m.eleme && !('gecmis' in m.eleme) ? m.eleme : null;
          return (
            <View style={[s.balon, ben ? { alignSelf: 'flex-end', backgroundColor: r.balonBen } : { alignSelf: 'flex-start', backgroundColor: r.balonO }]}>
              {grup && !ben ? <Text style={{ color: r.ana, fontSize: 12, fontWeight: '600' }}>{m.gonderen_adi}</Text> : null}
              {m.alinti ? (
                <View style={[s.alinti, { backgroundColor: r.alinti, borderLeftColor: r.ana }]}>
                  <Text style={{ color: r.ana, fontSize: 11, fontWeight: '600' }}>{m.alinti.gonderen}</Text>
                  <Text style={{ color: r.soluk, fontSize: 12 }} numberOfLines={2}>{m.alinti.metin}</Text>
                </View>
              ) : null}
              <Text style={{ color: r.yazi, fontSize: 15 }}>{m.metin}</Text>
              <Text style={[s.saat, { color: r.soluk }]}>{saat(m.zaman)}</Text>
              {e && e.onem === 'yuksek' ? (
                <Text style={{ color: e.aksiyon === 'uyar' ? r.sari : r.ana, fontSize: 12, marginTop: 4 }}>
                  {e.aksiyon === 'uyar' ? '⚠️ ' : '★ '}{e.ozet}{e.kural_notlari?.length ? `\n${e.kural_notlari.join(' ')}` : ''}
                </Text>
              ) : null}
            </View>
          );
        }}
        ListFooterComponent={veri?.taslaklar.length ? (
          <View style={{ marginTop: 10 }}>
            <Text style={{ color: r.soluk, fontSize: 11, fontWeight: '700', marginBottom: 6 }}>TULPAR'IN HAZIRLADIĞI TASLAK</Text>
            {veri.taslaklar.map((t) => <TaslakKart key={t.id} t={{ ...t, gelenler: veri.mesajlar.filter((m) => t.mesaj_idler.includes(m.id)) }} bitti={yenile} />)}
          </View>
        ) : undefined} />
    </View>
  );
}

const s = StyleSheet.create({
  modlar: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  modCip: { borderWidth: 1.5, borderRadius: 14, paddingHorizontal: 10, paddingVertical: 4 },
  balon: { borderRadius: 12, padding: 8, marginBottom: 6, maxWidth: '85%' },
  alinti: { borderLeftWidth: 3, borderRadius: 6, padding: 6, marginBottom: 4 },
  saat: { fontSize: 10, alignSelf: 'flex-end', marginTop: 2 },
});
