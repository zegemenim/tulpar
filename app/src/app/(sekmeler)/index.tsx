// Ana ekran: Tulpar'la konuşma (sesli/yazılı), onay bekleyenler, bekleyen taslaklar, son önemli mesajlar.
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, KeyboardAvoidingView, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import * as SecureStore from 'expo-secure-store';
import { Ionicons } from '@expo/vector-icons';
import GuncellemeSeridi from '../../bilesenler/GuncellemeSeridi';
import OnayKart from '../../bilesenler/OnayKart';
import { Ana, AsistanMesaj, istek, saat } from '../../lib/api';
import { yokla } from '../../lib/bildirim';
import { dinlemeBekliyorMu, dinlemeyeAbone } from '../../lib/dinleIstegi';
import { durumYazisi, Konusma, useSesliAsistan } from '../../lib/ses';
import { useRenk } from '../../lib/tema';


export default function AnaEkran() {
  const r = useRenk();
  const [ana, setAna] = useState<Ana | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [konusma, setKonusma] = useState<Konusma[]>([]);
  const [yazi, setYazi] = useState('');
  const [yukleniyor, setYukleniyor] = useState(false);
  const basili = useRef(false);  // uzun bas-konuş-bırak
  const eklendi = useCallback((k: Konusma) => setKonusma((x) => [...x.slice(-40), k]), []);
  const guncellendi = useCallback((metin: string, eylem?: Konusma['eylem']) =>
    setKonusma((x) => x.map((k, i) => (i === x.length - 1 && k.kim === 'tulpar' ? { ...k, metin, eylem: eylem ?? k.eylem } : k))), []);
  const asistan = useSesliAsistan(eklendi, guncellendi);

  const yenile = useCallback(async () => {
    setYukleniyor(true);
    try {
      setAna(await istek<Ana>('/ana', undefined, 20000));
      setHata(null);
      yokla().catch(() => {});
    } catch (e: any) {
      setHata(e.message);
    } finally {
      setYukleniyor(false);
    }
  }, []);

  useFocusEffect(useCallback(() => {
    yenile();
    const z = setInterval(yenile, 20000);
    return () => clearInterval(z);
  }, [yenile]));

  // Sadece asistan olarak açılınca (güç tuşu / sesle uyandırma: tulpar://dinle) otomatik dinle; elle açınca değil
  const { dinle, sohbet } = useLocalSearchParams<{ dinle?: string; sohbet?: string }>();

  // Geçmişten bir sohbet seçildiyse onu yükle ve oradan devam et
  useEffect(() => {
    if (!sohbet) return;
    istek<{ mesajlar: AsistanMesaj[] }>(`/asistan/sohbet/${sohbet}`).then((v) => {
      setKonusma(v.mesajlar.map((m) => ({ kim: m.rol, metin: m.metin, eylem: m.eylem })));
      asistan.setSohbetId(Number(sohbet));
    }).catch(() => {});
  }, [sohbet]);
  const yeniSohbet = () => { asistan.sustur(); setKonusma([]); asistan.setSohbetId(null); };
  // Güç tuşu / "Kâhya" ile açıldı: bekleyen "dinle" isteği varsa (ekran açılırken veya sonradan gelirse) dinlemeye başla
  const baslaRef = useRef(asistan.basla);
  baslaRef.current = asistan.basla;
  const dinlemeyiDene = useCallback(() => {
    if (!dinlemeBekliyorMu()) return;
    SecureStore.getItemAsync('acilista_dinle').then((v) => { if (v !== 'hayir') baslaRef.current(); });
  }, []);
  useEffect(() => { dinlemeyiDene(); return dinlemeyeAbone(dinlemeyiDene); }, [dinlemeyiDene]);
  useFocusEffect(useCallback(() => { dinlemeyiDene(); }, [dinlemeyiDene]));
  useEffect(() => {  // arka plandan öne gelince (asistan olarak açıldıysa istek dosyası bekliyor)
    const abone = AppState.addEventListener('change', (d) => { if (d === 'active') dinlemeyiDene(); });
    return () => abone.remove();
  }, [dinlemeyiDene]);

  useEffect(() => { if (konusma.at(-1)?.eylem) yenile(); }, [konusma, yenile]);

  const mikrofon = () => {
    if (asistan.durum === 'dinliyor') asistan.bitir();
    else if (asistan.durum === 'konusuyor') asistan.sustur();
    else if (asistan.durum === 'bos') asistan.basla();
  };
  const yaziGonder = () => {
    const m = yazi.trim();
    if (!m) return;
    setYazi('');
    asistan.sor(m, false);
  };

  const dinliyor = asistan.durum === 'dinliyor';
  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: r.zemin }} behavior="height">
      <ScrollView contentContainerStyle={s.icerik}
        refreshControl={<RefreshControl refreshing={yukleniyor} onRefresh={yenile} />}>
        <GuncellemeSeridi />
        {hata ? <Text style={[s.hata, { color: r.kirmizi }]}>Sunucuya ulaşılamadı: {hata}</Text> : null}

        {ana && ana.taslak_sayisi > 0 && (
          <Pressable onPress={() => router.push('/taslaklar')} style={[s.serit, { backgroundColor: r.ana }]}>
            <Ionicons name="create" size={18} color={r.anaYazi} />
            <Text style={{ color: r.anaYazi, fontWeight: '700', flex: 1 }}>{ana.taslak_sayisi} taslak onayını bekliyor</Text>
            <Ionicons name="chevron-forward" size={18} color={r.anaYazi} />
          </Pressable>
        )}

        <Text style={[s.bolum, { color: r.soluk }]}>ONAY BEKLEYENLER</Text>
        {ana?.onaylar.length ? ana.onaylar.map((o) => <OnayKart key={o.id} o={o} bitti={yenile} />)
          : <Text style={{ color: r.soluk, marginBottom: 8 }}>Onay bekleyen bir şey yok.</Text>}

        <View style={s.sohbetSatir}>
          <Text style={[s.bolum, { color: r.soluk, marginTop: 0, marginBottom: 0, flex: 1 }]}>
            {asistan.sohbetId ? 'SOHBET (devam ediyor)' : 'YENİ SOHBET'}
          </Text>
          <Pressable onPress={() => router.push('/sohbetler')} style={[s.kucukDugme, { borderColor: r.cizgi }]}>
            <Ionicons name="time-outline" size={16} color={r.ana} /><Text style={{ color: r.ana, fontSize: 13 }}>Geçmiş</Text>
          </Pressable>
          {konusma.length > 0 && (
            <Pressable onPress={yeniSohbet} style={[s.kucukDugme, { borderColor: r.cizgi }]}>
              <Ionicons name="add" size={16} color={r.ana} /><Text style={{ color: r.ana, fontSize: 13 }}>Yeni</Text>
            </Pressable>
          )}
        </View>
        {konusma.map((k, i) => (
          <View key={i} style={[s.balon, k.kim === 'ben' ? { alignSelf: 'flex-end', backgroundColor: r.balonBen } : { alignSelf: 'flex-start', backgroundColor: r.kart }]}>
            <Text style={{ color: r.yazi, fontSize: 15 }}>{k.metin}</Text>
            {k.eylem ? <Text style={{ color: r.ana, fontSize: 12, marginTop: 4 }}>{k.eylem.tur === 'gorev' ? '✓ görevlere eklendi' : k.eylem.tur === 'ekran' ? '🖥 ikinci ekran'
              : k.eylem.tur === 'taslak' ? '✉ taslak hazır, Taslaklar sekmesinden onayla' : k.eylem.tur === 'arastirma' ? '🔎 araştırılıyor, bitince bildirim gelecek' : k.eylem.tur === 'arastirma_sonuc' ? '🔎 araştırma sonucu'
              : '⏳ onayına sunuldu'}</Text> : null}
          </View>
        ))}

        {ana && ana.onemli.length > 0 && <Text style={[s.bolum, { color: r.soluk }]}>SON 24 SAATTE ÖNEMLİ</Text>}
        {ana?.onemli.slice(0, 10).map((m) => (
          <Pressable key={m.id} onPress={() => router.push({ pathname: '/sohbet/[id]', params: { id: m.sohbet_id, ad: m.sohbet_adi } })}
            style={[s.onemli, { backgroundColor: r.kart, borderColor: m.eleme?.aksiyon === 'uyar' ? r.sari : r.cizgi }]}>
            <Text style={{ color: r.yazi, fontWeight: '600' }} numberOfLines={1}>{m.eleme?.aksiyon === 'uyar' ? '⚠️ ' : ''}{m.sohbet_adi}</Text>
            <Text style={{ color: r.soluk }} numberOfLines={2}>{m.eleme?.ozet || m.metin}</Text>
            <Text style={{ color: r.soluk, fontSize: 11 }}>{saat(m.zaman)}</Text>
          </Pressable>
        ))}
      </ScrollView>

      <View style={[s.alt, { backgroundColor: r.kart, borderTopColor: r.cizgi }]}>
        {asistan.hata ? <Text style={{ color: r.kirmizi, marginBottom: 6 }}>{asistan.hata}</Text> : null}
        <Text style={{ color: dinliyor ? r.kirmizi : r.soluk, textAlign: 'center', marginBottom: 8 }}>{durumYazisi[asistan.durum]}</Text>
        <View style={s.girdiSatir}>
          <TextInput value={yazi} onChangeText={setYazi} onSubmitEditing={yaziGonder} returnKeyType="send"
            placeholder="Tulpar'a yaz…" placeholderTextColor={r.soluk}
            style={[s.girdi, { color: r.yazi, backgroundColor: r.zemin, borderColor: r.cizgi }]} />
          <Pressable onPress={mikrofon} onLongPress={() => { basili.current = true; asistan.basla(); }}
            onPressOut={() => { if (basili.current) { basili.current = false; asistan.bitir(); } }}
            style={[s.mik, { backgroundColor: dinliyor ? r.kirmizi : r.ana }]}>
            <Ionicons name={dinliyor ? 'stop' : asistan.durum === 'konusuyor' ? 'volume-mute' : 'mic'} size={28} color="#fff" />
          </Pressable>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  icerik: { padding: 14, paddingBottom: 24 },
  hata: { marginBottom: 10 },
  serit: { flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 12, padding: 12, marginBottom: 14 },
  bolum: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5, marginTop: 10, marginBottom: 6 },
  balon: { borderRadius: 14, padding: 10, marginBottom: 6, maxWidth: '88%' },
  onemli: { borderWidth: 1, borderRadius: 12, padding: 10, marginBottom: 6, gap: 2 },
  sohbetSatir: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 14, marginBottom: 6 },
  kucukDugme: { flexDirection: 'row', alignItems: 'center', gap: 4, borderWidth: 1, borderRadius: 14, paddingHorizontal: 10, paddingVertical: 4 },
  alt: { padding: 12, borderTopWidth: 1 },
  girdiSatir: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  girdi: { flex: 1, borderWidth: 1, borderRadius: 22, paddingHorizontal: 14, paddingVertical: 10, fontSize: 15 },
  mik: { width: 60, height: 60, borderRadius: 30, alignItems: 'center', justifyContent: 'center' },
});
