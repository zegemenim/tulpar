// Bir taslak: hangi mesajlara cevap, özet, uyarılar ve seçenekler. Gönderim her zaman ayrıca onay ister.
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import SesliGirdi from './SesliGirdi';
import { istek, saat, Taslak, TaslakMesaj } from '../lib/api';
import { useRenk } from '../lib/tema';

export default function TaslakKart({ t, bitti }: { t: Taslak; bitti: () => void }) {
  const r = useRenk();
  const [secili, setSecili] = useState(0);
  const [duzenle, setDuzenle] = useState(false);
  const [metin, setMetin] = useState('');
  const [mesgul, setMesgul] = useState(false);
  const [redPaneli, setRedPaneli] = useState(false);
  const [neden, setNeden] = useState('');
  const gelenler = t.gelenler ?? [];
  const alinti = (id: string | null) => gelenler.find((g) => g.id === id);
  const uyarilar = t.uyarilar.filter((u): u is string => typeof u === 'string');
  const sec = t.mesajlar[secili];

  const gonder = (mesajlar: TaslakMesaj[] | null) => {
    const giden = mesajlar ?? sec?.mesajlar ?? [];
    if (giden.some((m) => m.metin.includes('['))) {
      return Alert.alert('Boşluk var', 'Bu seçenekte doldurulması gereken [boşluk] var. Düzenleyip gönder.');
    }
    Alert.alert(`${t.sohbet_adi} kişisine gönderilsin mi?`, giden.map((m) => '• ' + m.metin).join('\n'), [
      { text: 'Vazgeç', style: 'cancel' },
      {
        text: 'Gönder', onPress: async () => {
          setMesgul(true);
          try {
            await istek(`/taslak/${t.id}/gonder`, mesajlar ? { mesajlar, neden: neden.trim() || null } : { secenek: secili });
            bitti();
          } catch (e: any) {
            Alert.alert('Gönderilemedi', e.message);
          } finally {
            setMesgul(false);
          }
        },
      },
    ]);
  };

  // Reddedince sebebi sorulur (isteğe bağlı, yazarak veya sesle); Tulpar sonraki taslaklarda bundan ders alır
  const reddet = async () => {
    await istek(`/taslak/${t.id}/reddet`, { neden: neden.trim() || null });
    bitti();
  };

  const duzenliGonder = () => {
    const satirlar = metin.split('\n').map((s) => s.trim()).filter(Boolean);
    if (!satirlar.length) return;
    const hedef = sec?.mesajlar[0]?.yanit_id ?? t.mesaj_idler[t.mesaj_idler.length - 1] ?? null;
    gonder(satirlar.map((s, i) => ({ yanit_id: i === 0 ? hedef : null, metin: s })));
  };

  return (
    <View style={[s.kart, { backgroundColor: r.kart, borderColor: r.cizgi }]}>
      <View style={s.baslik}>
        <Text style={[s.kisi, { color: r.yazi }]} numberOfLines={1}>{t.sohbet_adi}</Text>
        <Text style={{ color: r.soluk, fontSize: 12 }}>{saat(t.olusturma)}</Text>
      </View>

      {t.onceki?.length ? (
        <>
          <Text style={[s.etiket, { color: r.soluk }]}>ÖNCESİNDE</Text>
          {t.onceki.map((o) => (
            <Text key={o.id} style={{ color: r.soluk, fontSize: 13, marginBottom: 2 }} numberOfLines={2}>
              <Text style={{ fontWeight: '600' }}>{o.benden ? 'Sen' : o.gonderen_adi}: </Text>{o.metin}
            </Text>
          ))}
        </>
      ) : null}
      <Text style={[s.etiket, { color: r.soluk, marginTop: t.onceki?.length ? 8 : 0 }]}>CEVAP BEKLEYEN</Text>
      {gelenler.map((g) => (
        <View key={g.id} style={[s.gelen, { backgroundColor: r.balonO, borderColor: r.cizgi }]}>
          <Text style={{ color: r.ana, fontSize: 12, fontWeight: '600' }}>{g.gonderen_adi}</Text>
          <Text style={{ color: r.yazi }}>{g.metin}</Text>
        </View>
      ))}
      {t.ozet ? <Text style={{ color: r.soluk, fontStyle: 'italic', marginTop: 6 }}>{t.ozet}</Text> : null}
      {uyarilar.map((u, i) => <Text key={i} style={{ color: r.sari, marginTop: 4 }}>⚠ {u}</Text>)}

      <Text style={[s.etiket, { color: r.soluk, marginTop: 12 }]}>CEVAP SEÇENEKLERİ</Text>
      <View style={s.secenekler}>
        {t.mesajlar.map((sc, i) => (
          <Pressable key={i} onPress={() => { setSecili(i); setDuzenle(false); }}
            style={[s.cip, { borderColor: r.ana, backgroundColor: i === secili ? r.ana : 'transparent' }]}>
            <Text style={{ color: i === secili ? r.anaYazi : r.ana, fontWeight: '600' }}>{sc.etiket}</Text>
          </Pressable>
        ))}
      </View>

      {!duzenle && sec?.mesajlar.map((m, i) => {
        const a = alinti(m.yanit_id);
        return (
          <View key={i} style={[s.giden, { backgroundColor: r.balonBen }]}>
            {a ? (
              <View style={[s.alinti, { backgroundColor: r.alinti, borderLeftColor: r.ana }]}>
                <Text style={{ color: r.ana, fontSize: 11, fontWeight: '600' }}>↪ {a.gonderen_adi} mesajına cevap</Text>
                <Text style={{ color: r.soluk, fontSize: 12 }} numberOfLines={2}>{a.metin}</Text>
              </View>
            ) : null}
            <Text style={{ color: r.yazi, fontSize: 15 }}>{m.metin}</Text>
          </View>
        );
      })}

      {duzenle && (
        <View style={{ gap: 8 }}>
          <SesliGirdi multiline autoFocus value={metin} onChangeText={setMetin} placeholder="Her satır ayrı mesaj olarak gider" />
          <SesliGirdi value={neden} onChangeText={setNeden} placeholder="Neden değiştirdin? (isteğe bağlı, Tulpar öğrenir)" />
        </View>
      )}

      {redPaneli && (
        <View style={[s.panel, { borderColor: r.cizgi, backgroundColor: r.zemin }]}>
          <Text style={{ color: r.yazi, fontWeight: '600', marginBottom: 6 }}>Neden uygun değil? (isteğe bağlı)</Text>
          <SesliGirdi value={neden} onChangeText={setNeden} placeholder="örn. hocaya böyle yazılmaz, cevap gerekmiyordu" />
          <View style={[s.butonlar, { marginTop: 8 }]}>
            <Pressable onPress={() => setRedPaneli(false)} style={[s.buton, { borderColor: r.cizgi }]}>
              <Text style={{ color: r.yazi }}>Vazgeç</Text>
            </Pressable>
            <Pressable onPress={reddet} style={[s.buton, s.ana, { backgroundColor: r.kirmizi }]}>
              <Text style={{ color: '#fff', fontWeight: '700' }}>✕ Reddet</Text>
            </Pressable>
          </View>
        </View>
      )}

      <View style={s.butonlar}>
        <Pressable onPress={() => { setRedPaneli(true); setDuzenle(false); }} style={[s.buton, { borderColor: r.cizgi }]}>
          <Text style={{ color: r.kirmizi, fontWeight: '600' }}>✕ Reddet</Text>
        </Pressable>
        <Pressable onPress={() => { setDuzenle(!duzenle); setMetin((sec?.mesajlar ?? []).map((m) => m.metin).join('\n')); }}
          style={[s.buton, { borderColor: r.cizgi }]}>
          <Text style={{ color: r.yazi, fontWeight: '600' }}>{duzenle ? 'Vazgeç' : '✎ Düzenle'}</Text>
        </Pressable>
        <Pressable disabled={mesgul} onPress={() => (duzenle ? duzenliGonder() : gonder(null))}
          style={[s.buton, s.ana, { backgroundColor: r.yesil, opacity: mesgul ? 0.5 : 1 }]}>
          <Text style={{ color: '#fff', fontWeight: '700' }}>✓ Gönder</Text>
        </Pressable>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  kart: { borderRadius: 14, borderWidth: 1, padding: 14, marginBottom: 12 },
  baslik: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  kisi: { fontSize: 17, fontWeight: '700', flex: 1, marginRight: 8 },
  etiket: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5, marginBottom: 4 },
  gelen: { borderRadius: 10, borderWidth: 1, padding: 8, marginBottom: 4 },
  secenekler: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 },
  cip: { borderWidth: 1.5, borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6 },
  giden: { borderRadius: 10, padding: 8, marginBottom: 4, alignSelf: 'flex-end', maxWidth: '92%' },
  alinti: { borderLeftWidth: 3, borderRadius: 6, padding: 6, marginBottom: 4 },
  butonlar: { flexDirection: 'row', gap: 8, marginTop: 10 },
  buton: { flex: 1, borderWidth: 1, borderRadius: 10, paddingVertical: 10, alignItems: 'center' },
  ana: { borderWidth: 0 },
  panel: { borderWidth: 1, borderRadius: 10, padding: 10, marginTop: 10 },
});
