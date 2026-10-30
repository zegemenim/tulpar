// Sesli konuşma: kaydet -> HP'de Whisper ile yazıya dök -> Tulpar'a sor -> cevabı sesli oku.
import { useCallback, useEffect, useState } from 'react';
import { AudioModule, RecordingPresets, setAudioModeAsync, useAudioRecorder } from 'expo-audio';
import * as Speech from 'expo-speech';
import * as Haptics from 'expo-haptics';
import { istek, sesGonder } from './api';

export type Durum = 'bos' | 'dinliyor' | 'yaziya' | 'dusunuyor' | 'konusuyor';
export type Konusma = { kim: 'ben' | 'tulpar'; metin: string; eylem?: { tur: string; id: number } | null };

export function useSesliAsistan(eklendi: (k: Konusma) => void) {
  const kayit = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [durum, setDurum] = useState<Durum>('bos');
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    AudioModule.requestRecordingPermissionsAsync();
    setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
  }, []);

  /** Yazılı veya sesten çıkan metni Tulpar'a sorar. */
  const sor = useCallback(async (metin: string, sesliCevap: boolean) => {
    eklendi({ kim: 'ben', metin });
    setDurum('dusunuyor');
    try {
      const c = await istek<{ cevap: string; eylem: Konusma['eylem'] }>('/konus', { metin });
      eklendi({ kim: 'tulpar', metin: c.cevap, eylem: c.eylem });
      if (sesliCevap) {
        setDurum('konusuyor');
        Speech.speak(c.cevap, { language: 'tr-TR', onDone: () => setDurum('bos'), onStopped: () => setDurum('bos') });
      } else setDurum('bos');
    } catch (e: any) {
      setHata(e.message);
      setDurum('bos');
    }
  }, [eklendi]);

  const basla = useCallback(async () => {
    setHata(null);
    Speech.stop();
    const izin = await AudioModule.requestRecordingPermissionsAsync();
    if (!izin.granted) return setHata('Mikrofon izni yok');
    await kayit.prepareToRecordAsync();
    kayit.record();
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setDurum('dinliyor');
  }, [kayit]);

  const bitir = useCallback(async () => {
    if (durum !== 'dinliyor') return;
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
  }, [durum, kayit, sor]);

  return { durum, hata, basla, bitir, sor, sustur: () => { Speech.stop(); setDurum('bos'); } };
}

export const durumYazisi: Record<Durum, string> = {
  bos: 'Konuşmak için bas', dinliyor: 'Dinliyorum… bitirince bırak / bas', yaziya: 'Yazıya döküyorum…',
  dusunuyor: 'Düşünüyorum…', konusuyor: 'Konuşuyorum (susturmak için bas)',
};
