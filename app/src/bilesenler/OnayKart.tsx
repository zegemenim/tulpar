// Onay bekleyen iş (takvim, iş isteği, güvenlik uyarısı): ✓ onayla, ✕ reddet (reddedilenler 7 gün saklanır).
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { istek, Onay, saat } from '../lib/api';
import { useRenk } from '../lib/tema';

const SIMGE: Record<Onay['tur'], string> = { claude_gorev: '🛠', takvim: '📅', uyari: '⚠️', taslak_teklif: '💬' };

export default function OnayKart({ o, bitti, geriAl }: { o: Onay; bitti: () => void; geriAl?: boolean }) {
  const r = useRenk();
  const karar = async (k: 'onay' | 'red' | 'geri') => {
    await istek(`/onay/${o.id}`, { karar: k });
    bitti();
  };
  const v = o.veri || {};
  const zaman = [v.tarih, v.saat].filter(Boolean).join(' ');
  return (
    <View style={[s.kart, { backgroundColor: r.kart, borderColor: o.tur === 'uyari' ? r.sari : r.cizgi }]}>
      <Text style={s.simge}>{SIMGE[o.tur] ?? '•'}</Text>
      <View style={{ flex: 1 }}>
        <Text style={{ color: r.yazi, fontWeight: '600' }}>{o.baslik}</Text>
        {zaman ? <Text style={{ color: r.ana, marginTop: 2 }}>{zaman}</Text> : null}
        <Text style={{ color: r.soluk, fontSize: 12, marginTop: 2 }} numberOfLines={3}>{o.aciklama}</Text>
        <Text style={{ color: r.soluk, fontSize: 11, marginTop: 4 }}>{saat(o.olusturma)}</Text>
      </View>
      {geriAl ? (
        <Pressable onPress={() => karar('geri')} style={[s.dugme, { borderColor: r.cizgi }]}>
          <Text style={{ color: r.ana }}>↺</Text>
        </Pressable>
      ) : (
        <View style={{ gap: 6 }}>
          <Pressable accessibilityLabel="Onayla" onPress={() => karar('onay')} style={[s.dugme, { backgroundColor: r.yesil }]}>
            <Text style={s.isaret}>✓</Text>
          </Pressable>
          <Pressable accessibilityLabel="Reddet" onPress={() => karar('red')} style={[s.dugme, { backgroundColor: r.kirmizi }]}>
            <Text style={s.isaret}>✕</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  kart: { flexDirection: 'row', gap: 10, borderWidth: 1, borderRadius: 12, padding: 12, marginBottom: 8, alignItems: 'center' },
  simge: { fontSize: 22 },
  dugme: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', borderWidth: 0 },
  isaret: { color: '#fff', fontSize: 18, fontWeight: '700' },
});
