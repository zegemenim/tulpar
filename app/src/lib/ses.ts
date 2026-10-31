// Sesli konuşma: kaydet -> HP'de Whisper ile yazıya dök -> Tulpar'a sor -> cevabı sesli oku.
import { useCallback, useEffect, useRef, useState } from 'react';
import { AudioModule, RecordingPresets, setAudioModeAsync, useAudioRecorder } from 'expo-audio';
import * as Speech from 'expo-speech';
import * as Haptics from 'expo-haptics';
import * as SecureStore from 'expo-secure-store';
import { konusAkis, sesGonder } from './api';

export type Durum = 'bos' | 'dinliyor' | 'yaziya' | 'dusunuyor' | 'konusuyor';
export type Konusma = { kim: 'ben' | 'tulpar'; metin: string; eylem?: { tur: string; id: number } | null };

/** eklendi: yeni balon; guncellendi: son Tulpar balonunun metni (akarken) değişti. */
// Eller serbest dinleme: konuşma bitince (sessizlik) kendiliğinden durur; hiç konuşulmazsa vazgeçer
const SESSIZ_DB = -42;          // bunun altı sessizlik sayılır
const SON_SESSIZLIK_MS = 1600;  // konuştuktan sonra bu kadar sessizlik: bitti
const HIC_KONUSMAZSA_MS = 8000; // açıldıktan sonra bu sürede konuşma başlamazsa kapat

export function useSesliAsistan(eklendi: (k: Konusma) => void, guncellendi?: (metin: string, eylem?: Konusma['eylem']) => void) {
  const kayit = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, isMeteringEnabled: true });
  const [durum, setDurumState] = useState<Durum>('bos');
  const durumRef = useRef<Durum>('bos');  // basılı tut-bırak'ta güncel durumu görmek için
  const setDurum = useCallback((d: Durum) => { durumRef.current = d; setDurumState(d); }, []);
  const [hata, setHata] = useState<string | null>(null);
  const sohbetRef = useRef<number | null>(null);  // devam eden sohbet: Tulpar önceki mesajları hatırlar
  const [sohbetId, setSohbetIdState] = useState<number | null>(null);
  const setSohbetId = useCallback((id: number | null) => { sohbetRef.current = id; setSohbetIdState(id); }, []);
  const basladiRef = useRef<() => void>(() => {});
  const bitirRef = useRef<() => void>(() => {});

  useEffect(() => {
    AudioModule.requestRecordingPermissionsAsync();
    setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
  }, []);

  /** Yazılı veya sesten çıkan metni Tulpar'a sorar. Cevap akarken gösterilir; sesli sorularda cümle cümle
   *  hemen okunmaya başlanır (bütün cevabı beklemeden). */
  const sor = useCallback(async (metin: string, sesliCevap: boolean) => {
    eklendi({ kim: 'ben', metin });
    setDurum('dusunuyor');
    let tum = '';
    let okunan = 0;  // tum içinde sesli okunmuş kısmın sonu
    let eylem: Konusma['eylem'] = null;
    let konusuyor = false;
    let soruSordu = false;
    const oku = (son: boolean) => {
      if (!sesliCevap) return;
      const kalan = tum.slice(okunan);
      // tamamlanmış cümleleri oku; sonda kalan yarım cümleyi bekle (cevap bitince hepsi okunur)
      const m = son ? kalan.length : Math.max(kalan.lastIndexOf('. '), kalan.lastIndexOf('? '), kalan.lastIndexOf('! '), kalan.lastIndexOf('\n')) + 1;
      if (m <= 0) return;
      const cumle = kalan.slice(0, m).trim();
      okunan += m;
      if (!cumle) return;
      if (!konusuyor) { konusuyor = true; setDurum('konusuyor'); }
      Speech.speak(cumle, { language: 'tr-TR' });
    };
    try {
      let ilk = true;
      await konusAkis(metin, (o) => {
        if (o.tur === 'basladi' && o.sohbet_id) setSohbetId(o.sohbet_id);
        if (o.tur === 'son') soruSordu = !!o.soru;
        if (o.tur === 'eylem') eylem = o.eylem ?? null;
        if (o.tur === 'parca' && o.metin) {
          tum += o.metin;
          if (ilk) { eklendi({ kim: 'tulpar', metin: tum, eylem }); ilk = false; }
          else guncellendi?.(tum, eylem);
          oku(false);
        }
        if (o.tur === 'hata') setHata(o.metin ?? 'hata');
      }, sohbetRef.current);
      if (ilk) eklendi({ kim: 'tulpar', metin: tum || 'Şu an cevap veremedim.', eylem });
      oku(true);
      // Sesli konuşmada Tulpar soru sorduysa, okuması bitince mikrofon kendiliğinden açılır (ayarlardan kapatılabilir)
      const otomatikDinle = sesliCevap && soruSordu && (await SecureStore.getItemAsync('soruda_dinle')) !== 'hayir';
      if (!konusuyor) {
        setDurum('bos');
        if (otomatikDinle) basladiRef.current();
      } else {  // sıradaki cümlelerin okunması bitince "boş"a dön (veya cevabı dinle)
        const z = setInterval(async () => {
          if (!(await Speech.isSpeakingAsync())) {
            clearInterval(z);
            if (durumRef.current === 'konusuyor') { setDurum('bos'); if (otomatikDinle) basladiRef.current(); }
          }
        }, 400);
      }
    } catch (e: any) {
      setHata(e.message);
      setDurum('bos');
    }
  }, [eklendi, guncellendi, setDurum, setSohbetId]);

  const basla = useCallback(async () => {
    setHata(null);
    Speech.stop();
    const izin = await AudioModule.requestRecordingPermissionsAsync();
    if (!izin.granted) return setHata('Mikrofon izni yok');
    await kayit.prepareToRecordAsync();
    kayit.record();
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setDurum('dinliyor');
    const baslangic = Date.now();
    let konustu = false, sonSes = Date.now();
    const izle = setInterval(() => {
      if (durumRef.current !== 'dinliyor') return clearInterval(izle);
      const db = kayit.getStatus().metering ?? -160;
      if (db > SESSIZ_DB) { konustu = true; sonSes = Date.now(); }
      if (konustu && Date.now() - sonSes > SON_SESSIZLIK_MS) { clearInterval(izle); bitirRef.current(); }
      else if (!konustu && Date.now() - baslangic > HIC_KONUSMAZSA_MS) {
        clearInterval(izle); kayit.stop(); setDurum('bos');  // kimse konuşmadı: gönderme
      }
    }, 250);
  }, [kayit, setDurum]);

  const bitir = useCallback(async () => {
    if (durumRef.current !== 'dinliyor') return;
    await kayit.stop();
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (!kayit.uri) return setDurum('bos');
    setDurum('yaziya');
    try {
      const metin = (await sesGonder(kayit.uri)).trim();
      if (!metin) {
        setHata('Ses anlaşılamadı, tekrar dener misin?');
        return setDurum('bos');
      }
      await sor(metin, true);
    } catch (e: any) {
      setHata(e.message);
      setDurum('bos');
    }
  }, [kayit, sor, setDurum]);

  basladiRef.current = basla;
  bitirRef.current = bitir;
  return { durum, hata, basla, bitir, sor, sohbetId, setSohbetId, sustur: () => { Speech.stop(); setDurum('bos'); } };
}

export const durumYazisi: Record<Durum, string> = {
  bos: 'Konuşmak için bas', dinliyor: 'Dinliyorum… sustuğunda gönderirim', yaziya: 'Yazıya döküyorum…',
  dusunuyor: 'Düşünüyorum…', konusuyor: 'Konuşuyorum (susturmak için bas)',
};

/** Bir yazı alanını sesle doldurmak için: bas-konuş-bas, söylenen metin alana gelir (HP'de Whisper). */
export function useSesleYaz(metinGeldi: (metin: string) => void) {
  const kayit = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [durum, setDurum] = useState<'bos' | 'dinliyor' | 'yaziya'>('bos');
  const durumRef = useRef(durum);
  const ayarla = (d: typeof durum) => { durumRef.current = d; setDurum(d); };
  const [hata, setHata] = useState<string | null>(null);

  const dokun = useCallback(async () => {
    setHata(null);
    if (durumRef.current === 'bos') {
      const izin = await AudioModule.requestRecordingPermissionsAsync();
      if (!izin.granted) return setHata('Mikrofon izni yok');
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
      await kayit.prepareToRecordAsync();
      kayit.record();
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      ayarla('dinliyor');
    } else if (durumRef.current === 'dinliyor') {
      await kayit.stop();
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      if (!kayit.uri) return ayarla('bos');
      ayarla('yaziya');
      try {
        const metin = (await sesGonder(kayit.uri)).trim();
        if (metin) metinGeldi(metin); else setHata('Anlaşılamadı, tekrar dener misin?');
      } catch (e: any) {
        setHata(e.message);
      } finally {
        ayarla('bos');
      }
    }
  }, [kayit, metinGeldi]);

  return { durum, hata, dokun };
}
