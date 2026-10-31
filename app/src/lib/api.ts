// Tulpar sunucusuyla konuşma. Adres ve anahtar telefonda güvenli depoda (SecureStore) durur.
import * as SecureStore from 'expo-secure-store';
import { File, Paths } from 'expo-file-system';
import { fetch as akisFetch } from 'expo/fetch';

export type Ayar = { adres: string; anahtar: string; yedek?: string };  // yedek: ev ağı adresi (Tailscale çalışmazsa)

let onbellek: Ayar | null = null;

export async function ayarOku(): Promise<Ayar | null> {
  if (onbellek) return onbellek;
  const adres = await SecureStore.getItemAsync('adres');
  const anahtar = await SecureStore.getItemAsync('anahtar');
  const yedek = (await SecureStore.getItemAsync('yedek')) || undefined;
  onbellek = adres && anahtar ? { adres, anahtar, yedek } : null;
  return onbellek;
}

const temiz = (u?: string) => (u || '').trim().replace(/\/+$/, '');

export async function ayarYaz(a: Ayar) {
  const adres = temiz(a.adres);
  const yedek = temiz(a.yedek);
  await SecureStore.setItemAsync('adres', adres);
  await SecureStore.setItemAsync('anahtar', a.anahtar.trim());
  await SecureStore.setItemAsync('yedek', yedek);
  onbellek = { adres, anahtar: a.anahtar.trim(), yedek: yedek || undefined };
}

let calisanAdres: string | null = null;  // en son cevap veren adres önce denenir

/** Şu an bağlı olunan sunucunun ana makine adı (terminal/ekran gibi başka portlar için). */
export async function sunucuMakinesi(): Promise<string | null> {
  const a = await ayarOku();
  const adres = calisanAdres || a?.adres;
  return adres ? adres.replace(/^https?:\/\//, '').replace(/[:/].*$/, '') : null;
}

/** Hangi adres çalışıyor? Hızlı yoklama (/durum, kısa süre) ile bulur; asıl istek bundan sonra o adrese uzun süreyle gider.
 *  (Eskiden asıl isteğe kısa süre koyuyorduk: ses yazıya dökme gibi yavaş işler iptal edilip tekrarlanıyordu.) */
async function adresBul(a: Ayar): Promise<string[]> {
  const adaylar = [...new Set([calisanAdres, a.adres, a.yedek].filter(Boolean) as string[])];
  if (calisanAdres) return adaylar;  // en son çalışan önce; olmazsa getir() sıradakine geçer
  for (const adres of adaylar) {
    const kontrol = new AbortController();
    const z = setTimeout(() => kontrol.abort(), 5000);
    try {
      const y = await fetch(adres + '/durum', { headers: { 'x-tulpar-anahtar': a.anahtar }, signal: kontrol.signal });
      if (y.status < 500) { calisanAdres = adres; return [adres, ...adaylar.filter((x) => x !== adres)]; }
    } catch {} finally { clearTimeout(z); }
  }
  return adaylar;
}

async function getir(a: Ayar, yol: string, init: RequestInit, zamanAsimi: number, getirici: (u: string, i: any) => Promise<any> = fetch): Promise<Response> {
  const adresler = await adresBul(a);
  let sonHata: unknown;
  for (const adres of adresler) {
    const kontrol = new AbortController();
    const z = setTimeout(() => kontrol.abort(), zamanAsimi);
    try {
      const y = await getirici(adres + yol, { ...init, signal: kontrol.signal });
      calisanAdres = adres;
      return y;
    } catch (e) {
      sonHata = e;
      if (adres === calisanAdres) calisanAdres = null;  // çalışmıyor: bir dahaki sefere yeniden yokla
      if (kontrol.signal.aborted) break;  // uzun süre cevap gelmedi: aynı isteği başka adrese tekrar gönderme
    } finally {
      clearTimeout(z);
    }
  }
  throw sonHata instanceof Error ? sonHata : new Error('Sunucuya ulaşılamadı');
}

/** Bağlantı koparsa (ör. sunucu yeniden başlarken) 3 sn sonra bir kez daha dener. */
async function getirTekrarli(a: Ayar, yol: string, init: RequestInit, zamanAsimi: number, getirici?: (u: string, i: any) => Promise<any>): Promise<Response> {
  try {
    const y = await getir(a, yol, init, zamanAsimi, getirici);
    if (y.status < 500) return y;
  } catch {}
  await new Promise((r) => setTimeout(r, 3000));
  return getir(a, yol, init, zamanAsimi, getirici);
}

export async function istek<T = any>(yol: string, govde?: unknown, zamanAsimi = 200000): Promise<T> {
  const a = await ayarOku();
  if (!a) throw new Error('Sunucu ayarı yok');
  const y = await getirTekrarli(a, yol, {
    method: govde === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', 'x-tulpar-anahtar': a.anahtar },
    body: govde === undefined ? undefined : JSON.stringify(govde),
  }, zamanAsimi);
  if (!y.ok) throw new Error(`${y.status}: ${(await y.text()).slice(0, 200)}`);
  return (await y.json()) as T;
}

export type AkisOlay = { tur: 'basladi' | 'eylem' | 'parca' | 'hata' | 'son'; metin?: string; sohbet_id?: number; soru?: boolean; eylem?: { tur: string; id: number } | null; arac?: string };

/** Anlık konuşma: cevap üretildikçe her satırı (olayı) geri çağırır. */
export async function konusAkis(metin: string, olay: (o: AkisOlay) => void, sohbetId?: number | null): Promise<void> {
  const a = await ayarOku();
  if (!a) throw new Error('Sunucu ayarı yok');
  const y = await getir(a, '/konus-akis', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-tulpar-anahtar': a.anahtar },
    body: JSON.stringify({ metin, sohbet_id: sohbetId ?? null }),
  }, 200000, akisFetch);
  if (!y.ok || !y.body) throw new Error(`konuşma ${y.status}`);
  const okuyucu = y.body.getReader();
  const cozucu = new TextDecoder();
  let tampon = '';
  for (;;) {
    const { done, value } = await okuyucu.read();
    if (done) break;
    tampon += cozucu.decode(value, { stream: true });
    let i;
    while ((i = tampon.indexOf('\n')) >= 0) {
      const satir = tampon.slice(0, i).trim();
      tampon = tampon.slice(i + 1);
      if (satir) olay(JSON.parse(satir));
    }
  }
}

/** Ses kaydını sunucuya yollar, yazıya dökülmüş metni döner (ses HP'de işlenip silinir). */
export async function sesGonder(uri: string): Promise<string> {
  const a = await ayarOku();
  if (!a) throw new Error('Sunucu ayarı yok');
  const veri = await new File(uri).bytes();
  const y = await getirTekrarli(a, '/ses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/octet-stream', 'x-tulpar-anahtar': a.anahtar },
    body: veri,
  }, 200000);
  if (!y.ok) throw new Error(y.status >= 500 ? 'Sunucu yeniden başlıyor olabilir, birazdan tekrar dene.' : `ses ${y.status}`);
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
  onceki?: { id: string; gonderen_adi: string; benden: number; metin: string; zaman: number }[];
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

export type AsistanSohbet = { id: number; baslik: string; guncel: number; son: string | null };
export type AsistanMesaj = { id: number; rol: 'ben' | 'tulpar'; metin: string; eylem: { tur: string; id: number } | null; zaman: number };

/** Metni HP'de Türkçe sesle sentezletir; çalınabilir bir dosya yolu (uri) döner. */
export async function sentezle(metin: string): Promise<string> {
  const a = await ayarOku();
  if (!a) throw new Error('Sunucu ayarı yok');
  const y = await getirTekrarli(a, '/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-tulpar-anahtar': a.anahtar },
    body: JSON.stringify({ metin }),
  }, 60000);
  if (!y.ok) throw new Error(`tts ${y.status}`);
  const dosya = new File(Paths.cache, `tts-${Date.now()}-${Math.floor(Math.random() * 1e6)}.wav`);
  dosya.write(new Uint8Array(await y.arrayBuffer()));
  return dosya.uri;
}
