// HP'ye telefondan erişim: Terminal (ttyd + tmux; kapatınca oturum kaybolmaz) ve Ekran (yakında).
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { WebView } from 'react-native-webview';
import { istek, sunucuMakinesi } from '../../lib/api';
import { useRenk } from '../../lib/tema';

type Terminal = { port: number; kullanici: string; parola: string };
type Sekme = 'terminal' | 'ekran';

export default function Bilgisayar() {
  const r = useRenk();
  const [sekme, setSekme] = useState<Sekme>('terminal');
  const [bilgi, setBilgi] = useState<{ url: string; t: Terminal } | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [anahtar, setAnahtar] = useState(0);  // yeniden yüklemek için
  const [ekran, setEkran] = useState<string | null>(null);  // görünür tarayıcının noVNC adresi
  const [ekranHata, setEkranHata] = useState<string | null>(null);

  useFocusEffect(useCallback(() => {
    (async () => {
      try {
        const t = await istek<Terminal>('/terminal', undefined, 15000);
        const makine = await sunucuMakinesi();
        setBilgi({ url: `http://${makine}:${t.port}/`, t });
        setHata(null);
      } catch (e: any) {
        setHata(e.message);
      }
    })();
  }, []));

  useEffect(() => {  // Ekran sekmesi: görünür tarayıcıyı aç (kapalıysa), noVNC adresini hazırla
    if (sekme !== 'ekran') return;
    (async () => {
      try {
        await istek('/ekran/ac', { ac: true }, 30000);
        await new Promise((t) => setTimeout(t, 4000));
        const e = await istek<{ port: number; parola: string }>('/ekran', undefined, 15000);
        const makine = await sunucuMakinesi();
        setEkran(`http://${makine}:${e.port}/vnc.html?autoconnect=true&resize=scale&password=${encodeURIComponent(e.parola)}`);
        setEkranHata(null);
      } catch (x: any) {
        setEkranHata(x.message);
      }
    })();
  }, [sekme, anahtar]);

  return (
    <View style={{ flex: 1, backgroundColor: r.zemin }}>
      <View style={[s.sekmeler, { backgroundColor: r.kart, borderBottomColor: r.cizgi }]}>
        {(['terminal', 'ekran'] as Sekme[]).map((k) => (
          <Pressable key={k} onPress={() => setSekme(k)} style={[s.sekme, sekme === k && { borderBottomColor: r.ana }]}>
            <Text style={{ color: sekme === k ? r.ana : r.soluk, fontWeight: '700' }}>{k === 'terminal' ? 'Terminal' : 'Ekran'}</Text>
          </Pressable>
        ))}
        <Pressable onPress={() => setAnahtar((x) => x + 1)} style={s.yenile}>
          <Text style={{ color: r.ana }}>↻</Text>
        </Pressable>
      </View>

      {sekme === 'terminal' && (
        hata ? <Text style={[s.bilgi, { color: r.kirmizi }]}>Terminale bağlanılamadı: {hata}</Text>
          : !bilgi ? <ActivityIndicator style={{ marginTop: 40 }} />
            : (
              <WebView key={anahtar} source={{ uri: bilgi.url }} style={{ flex: 1, backgroundColor: '#000' }}
                basicAuthCredential={{ username: bilgi.t.kullanici, password: bilgi.t.parola }}
                keyboardDisplayRequiresUserAction={false} hideKeyboardAccessoryView={false}
                onError={(e) => setHata(e.nativeEvent.description)} />
            )
      )}

      {sekme === 'ekran' && (
        ekranHata ? <Text style={[s.bilgi, { color: r.kirmizi }]}>Ekrana bağlanılamadı: {ekranHata}</Text>
          : !ekran ? <ActivityIndicator style={{ marginTop: 40 }} />
            : <WebView key={anahtar} source={{ uri: ekran }} style={{ flex: 1, backgroundColor: '#000' }}
                onError={(e) => setEkranHata(e.nativeEvent.description)} />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  sekmeler: { flexDirection: 'row', borderBottomWidth: StyleSheet.hairlineWidth },
  sekme: { paddingHorizontal: 18, paddingVertical: 12, borderBottomWidth: 2, borderBottomColor: 'transparent' },
  yenile: { marginLeft: 'auto', paddingHorizontal: 18, justifyContent: 'center' },
  bilgi: { padding: 20, lineHeight: 20 },
});
