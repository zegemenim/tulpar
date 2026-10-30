// Bekleyen bütün taslaklar, en yenisi üstte.
import { useCallback, useState } from 'react';
import { FlatList, RefreshControl, Text, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import TaslakKart from '../../bilesenler/TaslakKart';
import { istek, Taslak } from '../../lib/api';
import { useRenk } from '../../lib/tema';

export default function Taslaklar() {
  const r = useRenk();
  const [liste, setListe] = useState<Taslak[]>([]);
  const [yuk, setYuk] = useState(false);
  const yenile = useCallback(async () => {
    setYuk(true);
    try { setListe(await istek<Taslak[]>('/taslaklar')); } catch {} finally { setYuk(false); }
  }, []);
  useFocusEffect(useCallback(() => { yenile(); }, [yenile]));

  return (
    <View style={{ flex: 1, backgroundColor: r.zemin }}>
      <FlatList data={liste} keyExtractor={(t) => String(t.id)} contentContainerStyle={{ padding: 12 }}
        refreshControl={<RefreshControl refreshing={yuk} onRefresh={yenile} />}
        ListEmptyComponent={<Text style={{ color: r.soluk, textAlign: 'center', marginTop: 40 }}>Bekleyen taslak yok.</Text>}
        renderItem={({ item }) => <TaslakKart t={item} bitti={yenile} />} />
    </View>
  );
}
