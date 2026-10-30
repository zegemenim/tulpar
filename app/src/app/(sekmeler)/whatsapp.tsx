// WhatsApp sohbet listesi: son mesaj, bekleyen taslak sayısı, sohbet modu.
import { useCallback, useMemo, useState } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, TextInput, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { istek, saat, Sohbet } from '../../lib/api';
import { useRenk } from '../../lib/tema';

const MOD_ETIKET = { tam: 'TAM', onemli: 'ÖNEMLİ', kapali: 'KAPALI' } as const;

export default function WhatsApp() {
  const r = useRenk();
  const [liste, setListe] = useState<Sohbet[]>([]);
  const [ara, setAra] = useState('');
  const [yuk, setYuk] = useState(false);
  const modRenk = { tam: r.yesil, onemli: r.sari, kapali: r.kirmizi };

  const yenile = useCallback(async () => {
    setYuk(true);
    try { setListe(await istek<Sohbet[]>('/sohbetler')); } catch {} finally { setYuk(false); }
  }, []);
  useFocusEffect(useCallback(() => { yenile(); }, [yenile]));

  const gorunen = useMemo(() => {
    const a = ara.trim().toLocaleLowerCase('tr');
    return a ? liste.filter((x) => x.sohbet_adi?.toLocaleLowerCase('tr').includes(a)) : liste;
  }, [ara, liste]);

  return (
    <View style={{ flex: 1, backgroundColor: r.zemin }}>
      <TextInput value={ara} onChangeText={setAra} placeholder="Sohbet ara" placeholderTextColor={r.soluk}
        style={[s.ara, { color: r.yazi, backgroundColor: r.kart, borderColor: r.cizgi }]} />
      <FlatList data={gorunen} keyExtractor={(x) => x.sohbet_id}
        refreshControl={<RefreshControl refreshing={yuk} onRefresh={yenile} />}
        renderItem={({ item: x }) => (
          <Pressable onPress={() => router.push({ pathname: '/sohbet/[id]', params: { id: x.sohbet_id, ad: x.sohbet_adi } })}
            style={[s.satir, { borderBottomColor: r.cizgi }]}>
            <View style={[s.avatar, { backgroundColor: r.alinti }]}>
              <Text style={{ color: r.yazi, fontWeight: '700' }}>{x.grup ? '👥' : (x.sohbet_adi || '?').slice(0, 1).toLocaleUpperCase('tr')}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <View style={s.ust}>
                <Text style={{ color: r.yazi, fontWeight: '600', flex: 1 }} numberOfLines={1}>{x.sohbet_adi}</Text>
                <Text style={{ color: r.soluk, fontSize: 12 }}>{saat(x.son_zaman)}</Text>
              </View>
              <View style={s.ust}>
                <Text style={{ color: r.soluk, flex: 1 }} numberOfLines={1}>
                  {x.grup && x.son_gonderen ? `${x.son_gonderen}: ` : ''}{x.son_metin}
                </Text>
                {x.taslak > 0 && <View style={[s.rozet, { backgroundColor: r.ana }]}><Text style={{ color: r.anaYazi, fontSize: 11, fontWeight: '700' }}>{x.taslak} taslak</Text></View>}
                <Text style={[s.mod, { color: modRenk[x.mod] }]}>{MOD_ETIKET[x.mod]}</Text>
              </View>
            </View>
          </Pressable>
        )} />
    </View>
  );
}

const s = StyleSheet.create({
  ara: { margin: 10, borderWidth: 1, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  satir: { flexDirection: 'row', gap: 10, paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth },
  avatar: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  ust: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  rozet: { borderRadius: 10, paddingHorizontal: 6, paddingVertical: 2 },
  mod: { fontSize: 10, fontWeight: '700' },
});
