// Tulpar'la geçmiş sohbetler (Claude/Gemini'deki gibi): dokun → kaldığın yerden devam et.
import { useCallback, useState } from 'react';
import { Alert, FlatList, Pressable, RefreshControl, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { AsistanSohbet, istek, saat } from '../lib/api';
import { useRenk } from '../lib/tema';

export default function Sohbetler() {
  const r = useRenk();
  const [liste, setListe] = useState<AsistanSohbet[]>([]);
  const [yuk, setYuk] = useState(false);
  const yenile = useCallback(async () => {
    setYuk(true);
    try { setListe(await istek<AsistanSohbet[]>('/asistan/sohbetler')); } catch {} finally { setYuk(false); }
  }, []);
  useFocusEffect(useCallback(() => { yenile(); }, [yenile]));

  const sil = (x: AsistanSohbet) => Alert.alert('Sohbet silinsin mi?', x.baslik, [
    { text: 'Vazgeç', style: 'cancel' },
    { text: 'Sil', style: 'destructive', onPress: async () => { await istek(`/asistan/sohbet/${x.id}/sil`, {}); yenile(); } },
  ]);

  return (
    <View style={{ flex: 1, backgroundColor: r.zemin }}>
      <FlatList data={liste} keyExtractor={(x) => String(x.id)} contentContainerStyle={{ padding: 12 }}
        refreshControl={<RefreshControl refreshing={yuk} onRefresh={yenile} />}
        ListEmptyComponent={<Text style={{ color: r.soluk, textAlign: 'center', marginTop: 40 }}>Henüz sohbet yok.</Text>}
        renderItem={({ item: x }) => (
          <Pressable onPress={() => router.navigate({ pathname: '/', params: { sohbet: String(x.id) } })} onLongPress={() => sil(x)}
            style={{ backgroundColor: r.kart, borderColor: r.cizgi, borderWidth: 1, borderRadius: 12, padding: 12, marginBottom: 8 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 8 }}>
              <Text style={{ color: r.yazi, fontWeight: '600', flex: 1 }} numberOfLines={1}>{x.baslik}</Text>
              <Text style={{ color: r.soluk, fontSize: 12 }}>{saat(x.guncel)}</Text>
            </View>
            {x.son ? <Text style={{ color: r.soluk, marginTop: 2 }} numberOfLines={2}>{x.son}</Text> : null}
          </Pressable>
        )} />
      <Text style={{ color: r.soluk, fontSize: 12, textAlign: 'center', padding: 8 }}>Silmek için basılı tut</Text>
    </View>
  );
}
