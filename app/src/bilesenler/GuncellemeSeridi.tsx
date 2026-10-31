// Yeni sürüm varsa üstte "Güncelle" şeridi.
import { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { denetle, indirVeKur, Surum } from '../lib/guncelleme';
import { useRenk } from '../lib/tema';

export default function GuncellemeSeridi() {
  const r = useRenk();
  const [yeni, setYeni] = useState<Surum | null>(null);
  const [iniyor, setIniyor] = useState(false);
  useEffect(() => { denetle().then(setYeni).catch(() => {}); }, []);
  if (!yeni) return null;
  const guncelle = async () => {
    setIniyor(true);
    try { await indirVeKur(); } catch (e: any) { Alert.alert('Güncellenemedi', e.message); } finally { setIniyor(false); }
  };
  return (
    <Pressable onPress={guncelle} disabled={iniyor}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: r.yesil, borderRadius: 12, padding: 12, marginBottom: 12 }}>
      {iniyor ? <ActivityIndicator color="#fff" /> : <Ionicons name="cloud-download" size={18} color="#fff" />}
      <Text style={{ color: '#fff', fontWeight: '700', flex: 1 }}>
        {iniyor ? 'İndiriliyor…' : `Yeni sürüm hazır${yeni.notlar ? `: ${yeni.notlar}` : ''} — Güncelle`}
      </Text>
    </Pressable>
  );
}
