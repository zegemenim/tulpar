// Uygulama içi güncelleme: yeni APK HP'de durur; uygulama sürümü karşılaştırır, indirir, Android kurulumunu açar.
// (Play Store dışı uygulamada son "Yükle" onayını Android her zaman kullanıcıya sorar.)
import * as Application from 'expo-application';
import { File, Paths } from 'expo-file-system';
import { startActivityAsync } from 'expo-intent-launcher';
import { ayarOku, istek, sunucuMakinesi } from './api';

export type Surum = { surum: number; boyut?: number; tarih?: string; notlar?: string };

export const mevcutSurum = () => Number(Application.nativeBuildVersion || 0);

export async function denetle(): Promise<Surum | null> {
  const s = await istek<Surum>('/uygulama/surum', undefined, 15000);
  return s.surum > mevcutSurum() ? s : null;
}

export async function indirVeKur(): Promise<void> {
  const a = await ayarOku();
  const makine = await sunucuMakinesi();
  if (!a || !makine) throw new Error('Sunucu ayarı yok');
  const port = a.adres.match(/:(\d+)/)?.[1] ?? '8090';
  const hedef = new File(Paths.cache, 'Tulpar-guncelleme.apk');
  if (hedef.exists) hedef.delete();
  const dosya = await File.downloadFileAsync(`http://${makine}:${port}/uygulama/apk`, hedef,
    { headers: { 'x-tulpar-anahtar': a.anahtar }, idempotent: true });
  await startActivityAsync('android.intent.action.VIEW', {
    data: dosya.contentUri,
    type: 'application/vnd.android.package-archive',
    flags: 1,  // FLAG_GRANT_READ_URI_PERMISSION
  });
}


/** Uyandırma için ses modellerini (Türkçe 37 MB + konuşmacı 13 MB) HP'den indirir; servis açılınca bunları kullanır. */
export async function sesModeliniIndir(): Promise<void> {
  const a = await ayarOku();
  const makine = await sunucuMakinesi();
  if (!a || !makine) throw new Error('Sunucu ayarı yok');
  const port = a.adres.match(/:(\d+)/)?.[1] ?? '8090';
  const indir = async (kurulu: string[], zip: string, yol: string) => {
    if (new File(Paths.document, ...kurulu).exists) return;  // zaten kurulu
    const hedef = new File(Paths.document, zip);
    if (hedef.exists) hedef.delete();  // yarım kalmış olabilir (zlib hatası): her seferinde baştan indir
    // Geçici ada iner, bitince taşınır: indirme sürerken servis başlarsa yarım zip'i açmaya çalışmasın
    const gecici = new File(Paths.document, zip + '.indiriliyor');
    if (gecici.exists) gecici.delete();
    await File.downloadFileAsync(`http://${makine}:${port}${yol}`, gecici, { headers: { 'x-tulpar-anahtar': a.anahtar }, idempotent: true });
    gecici.move(hedef);
  };
  await indir(['vosk-model-small-tr-0.3', 'conf'], 'vosk-tr.zip', '/uygulama/vosk');
  await indir(['vosk-model-spk-0.4'], 'vosk-spk.zip', '/uygulama/vosk-spk').catch(() => {});  // yoksa sadece "benim sesimle" çalışmaz
}
