// Tulpar'ın senin hakkında bildikleri: konuşmalardan kendisi öğrenir; buradan ekle, düzelt, sil.
import { useCallback, useState } from 'react';
import { Alert, FlatList, Pressable, Text, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import SesliGirdi from '../bilesenler/SesliGirdi';
import { istek, saat } from '../lib/api';
import { useRenk } from '../lib/tema';

type Bilgi = { id: number; bilgi: string; kaynak: string; guven: 'kesin' | 'tahmin'; guncel: number };

export default function Hakkimda() {
  const r = useRenk();
  const [liste, setListe] = useState<Bilgi[]>([]);
  const [yeni, setYeni] = useState('');
  const [duzenlenen, setDuzenlenen] = useState<Bilgi | null>(null);
  const yenile = useCallback(async () => { try { setListe(await istek<Bilgi[]>('/hafiza')); } catch {} }, []);
  useFocusEffect(useCallback(() => { yenile(); }, [yenile]));

  const kaydet = async () => {
    if (!yeni.trim()) return;
    await istek('/hafiza', duzenlenen ? { id: duzenlenen.id, bilgi: yeni } : { bilgi: yeni });
    setYeni(''); setDuzenlenen(null); yenile();
  };
  const sil = (b: Bilgi) => Alert.alert('Bu bilgi silinsin mi?', b.bilgi, [
    { text: 'Vazgeç', style: 'cancel' },
    { text: 'Sil', style: 'destructive', onPress: async () => { await istek(`/hafiza/${b.id}/sil`, {}); yenile(); } },
  ]);

  return (
    <View style={{ flex: 1, backgroundColor: r.zemin }}>
      <View style={{ padding: 12, gap: 8, backgroundColor: r.kart, borderBottomColor: r.cizgi, borderBottomWidth: 1 }}>
        <SesliGirdi value={yeni} onChangeText={setYeni} placeholder={duzenlenen ? 'Bilgiyi düzelt' : 'Yeni bilgi ekle (örn. Annemin doğum günü 12 Mart)'} />
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {duzenlenen && (
            <Pressable onPress={() => { setDuzenlenen(null); setYeni(''); }} style={{ flex: 1, borderWidth: 1, borderColor: r.cizgi, borderRadius: 10, padding: 10, alignItems: 'center' }}>
              <Text style={{ color: r.yazi }}>Vazgeç</Text>
            </Pressable>
          )}
          <Pressable onPress={kaydet} style={{ flex: 1, backgroundColor: r.ana, borderRadius: 10, padding: 10, alignItems: 'center' }}>
            <Text style={{ color: r.anaYazi, fontWeight: '700' }}>{duzenlenen ? 'Kaydet' : 'Ekle'}</Text>
          </Pressable>
        </View>
      </View>
      <FlatList data={liste} keyExtractor={(b) => String(b.id)} contentContainerStyle={{ padding: 12 }}
        ListEmptyComponent={<Text style={{ color: r.soluk, textAlign: 'center', marginTop: 30 }}>Tulpar henüz bir şey öğrenmedi. Konuştukça burası dolacak.</Text>}
        renderItem={({ item: b }) => (
          <Pressable onPress={() => { setDuzenlenen(b); setYeni(b.bilgi); }} onLongPress={() => sil(b)}
            style={{ backgroundColor: r.kart, borderColor: r.cizgi, borderWidth: 1, borderRadius: 10, padding: 12, marginBottom: 6 }}>
            <Text style={{ color: r.yazi }}>{b.bilgi}</Text>
            <Text style={{ color: r.soluk, fontSize: 11, marginTop: 4 }}>
              {b.guven === 'kesin' ? '✓ senin girdiğin' : 'Tulpar öğrendi'} · {b.kaynak} · {saat(b.guncel)}
            </Text>
          </Pressable>
        )} />
      <Text style={{ color: r.soluk, fontSize: 12, textAlign: 'center', padding: 8 }}>Düzeltmek için dokun, silmek için basılı tut</Text>
    </View>
  );
}
