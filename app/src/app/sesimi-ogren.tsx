// "Sesimi öğren": uyandırma servisi senin "Kâhya" / "Tulpar" demeni nasıl duyduğunu toplar ve bunları
// kişisel varyant listesine ekler (Google'ın "Hey Google" ses eğitimi gibi). Hepsi telefonda, çevrimdışı.
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Pressable, ScrollView, Switch, Text, View } from 'react-native';
import { File, Paths } from 'expo-file-system';
import { startActivityAsync } from 'expo-intent-launcher';
import { useRenk } from '../lib/tema';

const gonder = (islem: string) => startActivityAsync('android.intent.action.MAIN', {
  packageName: 'dev.tulpar.app', className: 'dev.tulpar.app.UyandirmaActivity', extra: { islem },
});
const oku = async (ad: string): Promise<string[]> => {
  const f = new File(Paths.document, ad);
  if (!f.exists) return [];
  return (await f.text()).split('\n').map((x) => x.trim()).filter(Boolean);
};

export default function SesimiOgren() {
  const r = useRenk();
  const [calisiyor, setCalisiyor] = useState(false);
  const [duyulan, setDuyulan] = useState<string[]>([]);
  const [varyant, setVaryant] = useState<string[]>([]);
  const [sesVar, setSesVar] = useState(false);
  const [yalnizBen, setYalnizBen] = useState(false);
  const zamanlayici = useRef<ReturnType<typeof setInterval> | null>(null);

  const yukle = useCallback(async () => {
    setVaryant(await oku('uyandirma_varyant.txt'));
    setSesVar(new File(Paths.document, 'uyandirma_ses.txt').exists);
    setYalnizBen(new File(Paths.document, 'uyandirma_yalniz_ben.txt').exists);
  }, []);
  const yalnizDegistir = async (v: boolean) => {
    const f = new File(Paths.document, 'uyandirma_yalniz_ben.txt');
    if (v) { if (!f.exists) f.create(); await f.write('1'); } else if (f.exists) f.delete();
    await gonder('yukle');
    setYalnizBen(v);
  };
  useEffect(() => { yukle(); return () => { if (zamanlayici.current) clearInterval(zamanlayici.current); }; }, [yukle]);

  const basla = async () => {
    try {
      await gonder('ogren_basla');
      setCalisiyor(true); setDuyulan([]);
      zamanlayici.current = setInterval(async () => setDuyulan(await oku('uyandirma_ogrenilen.txt')), 1200);
    } catch (e: any) {
      Alert.alert('Başlamadı', `${e.message}\nAyarlardan “Tulpar / Kâhya deyince aç” açık olmalı.`);
    }
  };
  const bitir = async () => {
    if (zamanlayici.current) clearInterval(zamanlayici.current);
    await gonder('ogren_bitir');
    setCalisiyor(false);
    setTimeout(yukle, 800);
  };
  const sil = async (v: string) => {
    const kalan = varyant.filter((x) => x !== v);
    await new File(Paths.document, 'uyandirma_varyant.txt').write(kalan.join('\n'));
    await gonder('yukle');
    setVaryant(kalan);
  };

  const kart = { backgroundColor: r.kart, borderColor: r.cizgi, borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 12 } as const;
  return (
    <ScrollView style={{ backgroundColor: r.zemin }} contentContainerStyle={{ padding: 14 }}>
      <View style={kart}>
        <Text style={{ color: r.yazi, fontWeight: '700', fontSize: 16, marginBottom: 6 }}>Nasıl çalışır?</Text>
        <Text style={{ color: r.soluk, lineHeight: 20 }}>
          1. Başla'ya bas.{'\n'}
          2. “Kâhya” de, bir saniye bekle, 5 kez tekrarla.{'\n'}
          3. Aynısını “Tulpar” için yap. Normal konuş: yakından, uzaktan, farklı tonlarda deneyebilirsin.{'\n'}
          4. Bitir'e bas. Telefonun seni nasıl duyduğu (ör. “dolar”, “kah ya”) kişisel listene eklenir ve bundan sonra bunlar da seni uyandırır.
        </Text>
      </View>

      <Pressable onPress={calisiyor ? bitir : basla}
        style={{ backgroundColor: calisiyor ? r.kirmizi : r.ana, borderRadius: 12, padding: 14, alignItems: 'center', marginBottom: 12 }}>
        <Text style={{ color: r.anaYazi, fontWeight: '700', fontSize: 16 }}>{calisiyor ? 'Bitir ve kaydet' : 'Başla'}</Text>
      </Pressable>

      {calisiyor && (
        <View style={kart}>
          <Text style={{ color: r.yazi, fontWeight: '600' }}>Dinliyorum… şimdi söyle</Text>
          <Text style={{ color: r.ana, marginTop: 6 }}>{duyulan.length ? `Duydukları: ${duyulan.join(', ')}` : '(henüz bir şey duymadı)'}</Text>
        </View>
      )}

      <View style={[kart, { flexDirection: 'row', alignItems: 'center', gap: 10 }]}>
        <View style={{ flex: 1 }}>
          <Text style={{ color: r.yazi, fontWeight: '700' }}>Sadece benim sesimle uyan</Text>
          <Text style={{ color: r.soluk, fontSize: 13 }}>
            {sesVar ? 'Ses parmak izin kayıtlı. Başkası “Kâhya” derse uyanmaz (Siri gibi). Cümle bitince doğruladığı için uyanma yarım saniye gecikir.'
              : 'Önce yukarıdan Başla/Bitir ile kendi sesini kaydet.'}
          </Text>
        </View>
        <Switch value={yalnizBen} disabled={!sesVar} onValueChange={yalnizDegistir} />
      </View>

      <View style={kart}>
        <Text style={{ color: r.yazi, fontWeight: '700', marginBottom: 6 }}>Öğrenilen varyantlar</Text>
        {varyant.length ? varyant.map((v) => (
          <View key={v} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 4 }}>
            <Text style={{ color: r.yazi, flex: 1 }}>{v}</Text>
            <Pressable onPress={() => sil(v)}><Text style={{ color: r.kirmizi }}>Sil</Text></Pressable>
          </View>
        )) : <Text style={{ color: r.soluk }}>Henüz yok.</Text>}
        <Text style={{ color: r.soluk, fontSize: 12, marginTop: 8 }}>
          Yanlışlıkla uyandıran sıradan bir kelime varsa (ör. “ol”, “ya”) buradan sil.
        </Text>
      </View>
    </ScrollView>
  );
}
