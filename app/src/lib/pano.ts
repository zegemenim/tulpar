// Pano eşitleme: uygulama açıkken (Android arka planda panoyu okutmaz) telefon panosu HP üzerinden diğer cihazlarla paylaşılır.
import { useEffect } from 'react';
import { AppState } from 'react-native';
import * as Pano from 'expo-clipboard';
import { istek } from './api';

export function usePano() {
  useEffect(() => {
    let son = '';
    let dur = false;
    const tur = async () => {
      if (AppState.currentState !== 'active') return;
      try {
        const yerel = (await Pano.getStringAsync()) ?? '';
        if (yerel && yerel !== son) {
          son = yerel;
          await istek('/pano', { metin: yerel, kaynak: 'telefon' }, 5000);
          return;
        }
        const uzak = await istek<{ metin: string; kaynak: string }>('/pano', undefined, 5000);
        if (uzak.metin && uzak.kaynak !== 'telefon' && uzak.metin !== son) {
          son = uzak.metin;
          await Pano.setStringAsync(uzak.metin);
        }
      } catch {}
    };
    const t = setInterval(() => { if (!dur) tur(); }, 3000);
    return () => { dur = true; clearInterval(t); };
  }, []);
}
