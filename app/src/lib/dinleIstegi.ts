// Asistan olarak açılınca (güç tuşu / "Kâhya") "hemen dinle" isteği. İki yoldan gelir:
// - dinle.tsx (tulpar://dinle) bellekteki sinyali yazar (uygulama zaten açıkken),
// - AsistanActivity "dinle_istegi" dosyasını yazar (uygulama kapalıyken açılışta bağlantı kaybolabiliyor).
// Ana ekran ikisine de bakar.
import { File, Paths } from 'expo-file-system';

let bekleyen = 0;
const dinleyiciler = new Set<() => void>();
const SURE_MS = 20000;

export const dinlemeIste = () => { bekleyen = Date.now(); dinleyiciler.forEach((f) => f()); };

/** İstek varsa (son 20 sn içinde) true döner ve isteği tüketir. */
export const dinlemeBekliyorMu = () => {
  let v = bekleyen > 0 && Date.now() - bekleyen < SURE_MS;
  bekleyen = 0;
  try {
    const f = new File(Paths.document, 'dinle_istegi');
    if (f.exists) {
      const zaman = Number(f.textSync());
      f.delete();
      if (Date.now() - zaman < SURE_MS) v = true;
    }
  } catch {}
  return v;
};

export const dinlemeyeAbone = (f: () => void) => { dinleyiciler.add(f); return () => { dinleyiciler.delete(f); }; };

/** Kayda başlamadan önce: uyandırma servisi mikrofonu tutuyorsa bırakmasını ister (servis bu dosyayı izler). */
export async function mikrofonuIste() {
  try {
    if (!new File(Paths.document, 'uyandirma_acik').exists) return;
    const f = new File(Paths.document, 'mikrofon_istegi');
    if (!f.exists) f.create();
    await f.write(String(Date.now()));
    await new Promise((r) => setTimeout(r, 300));  // servis mikrofonu bıraksın
  } catch {}
}
