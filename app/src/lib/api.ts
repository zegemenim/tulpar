// Tulpar sunucusuyla konuşma. Adres ve anahtar telefonda güvenli depoda (SecureStore) durur.
import * as SecureStore from 'expo-secure-store';
import { File } from 'expo-file-system';

export type Ayar = { adres: string; anahtar: string };

let onbellek: Ayar | null = null;

export async function ayarOku(): Promise<Ayar | null> {
  if (onbellek) return onbellek;
  const adres = await SecureStore.getItemAsync('adres');
  const anahtar = await SecureStore.getItemAsync('anahtar');
  onbellek = adres && anahtar ? { adres, anahtar } : null;
  return onbellek;
}

export async function ayarYaz(a: Ayar) {
  const adres = a.adres.trim().replace(/\/+$/, '');
  await SecureStore.setItemAsync('adres', adres);
  await SecureStore.setItemAsync('anahtar', a.anahtar.trim());
  onbellek = { adres, anahtar: a.anahtar.trim() };
}

export async function istek<T = any>(yol: string, govde?: unknown, zamanAsimi = 200000): Promise<T> {
  const a = await ayarOku();
  if (!a) throw new Error('Sunucu ayarı yok');
  const kontrol = new AbortController();
  const z = setTimeout(() => kontrol.abort(), zamanAsimi);
  try {
    const y = await fetch(a.adres + yol, {
      method: govde === undefined ? 'GET' : 'POST',
      headers: { 'Content-Type': 'application/json', 'x-tulpar-anahtar': a.anahtar },
      body: govde === undefined ? undefined : JSON.stringify(govde),
      signal: kontrol.signal,
    });
    if (!y.ok) throw new Error(`${y.status}: ${(await y.text()).slice(0, 200)}`);
    return (await y.json()) as T;
  } finally {
    clearTimeout(z);
  }
}

/** Ses kaydını sunucuya yollar, yazıya dökülmüş metni döner (ses HP'de işlenip silinir). */
export async function sesGonder(uri: string): Promise<string> {
  const a = await ayarOku();
  if (!a) throw new Error('Sunucu ayarı yok');
  const veri = await new File(uri).bytes();
  const y = await fetch(a.adres + '/ses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/octet-stream', 'x-tulpar-anahtar': a.anahtar },
    body: veri,
  });
  if (!y.ok) throw new Error(`ses ${y.status}`);
  return (await y.json()).metin as string;
}

// ---- sunucudan gelen veri tipleri ----
export type Eleme = { onem?: string; aksiyon?: string; ozet?: string; kural_notlari?: string[]; guvenlik?: string[] };
export type Mesaj = {
  id: string; sohbet_id: string; sohbet_adi: string; grup: number; gonderen_adi: string; benden: number;
  metin: string; zaman: number; alinti_id?: string | null; alinti?: { gonderen: string; metin: string } | null; eleme?: Eleme | null;
};
export type TaslakMesaj = { yanit_id: string | null; metin: string };
export type Secenek = { etiket: string; mesajlar: TaslakMesaj[] };
export type Taslak = {
  id: number; sohbet_id: string; sohbet_adi: string; ozet: string | null; mesaj_idler: string[];
  mesajlar: Secenek[]; uyarilar: (string | object)[]; olusturma: number;
  gelenler?: { id: string; gonderen_adi: string; metin: string; zaman: number }[];
};
export type Onay = {
  id: number; tur: 'claude_gorev' | 'takvim' | 'uyari' | 'taslak_teklif'; baslik: string; aciklama: string;
  sohbet_adi: string | null; durum: string; olusturma: number; karar: number | null; veri: Record<string, any>;
};
export type Gorev = { id: number; metin: string; zaman: string | null; durum: string; kaynak: string; olusturma: number };
export type Sohbet = {
  sohbet_id: string; sohbet_adi: string; grup: number; son_metin: string; son_gonderen: string;
  son_zaman: number; taslak: number; mod: 'tam' | 'onemli' | 'kapali';
};
export type Ana = { onaylar: Onay[]; taslak_sayisi: number; gorevler: Gorev[]; onemli: Mesaj[] };

export const saat = (t: number) => {
  const d = new Date(t * 1000);
  const bugun = new Date().toDateString() === d.toDateString();
  return bugun ? d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' });
};
