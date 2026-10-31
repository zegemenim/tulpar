// Asistan olarak açılınca (güç tuşu / "Kâhya") "hemen dinle" isteği. Yönlendirme parametresiyle taşımak sekmeli
// ekranda kayboluyordu; bu yüzden doğrudan bir sinyal: dinle.tsx isteği yazar, ana ekran okur.
let bekleyen = 0;
const dinleyiciler = new Set<() => void>();

export const dinlemeIste = () => { bekleyen = Date.now(); dinleyiciler.forEach((f) => f()); };

/** İstek varsa (son 20 sn içinde) true döner ve isteği tüketir. */
export const dinlemeBekliyorMu = () => {
  const v = bekleyen > 0 && Date.now() - bekleyen < 20000;
  bekleyen = 0;
  return v;
};

export const dinlemeyeAbone = (f: () => void) => { dinleyiciler.add(f); return () => { dinleyiciler.delete(f); }; };
